import re

class CumulativeMafiaSummarizer:
    def __init__(self, model_pipeline):
        # Initial game setup
        self.game_setup = {
            'my_role': None,
            'my_team': None,
            'my_player_id': None,
            'all_players': [],
            'teammates': [],
            'setup_complete': False
        }
        self.model_pipeline = model_pipeline
        self.init_summary = ''        
        # Cumulative game history
        self.game_history = []  # List of round summaries
        self.current_round = 0
        
        # Current state
        self.alive_players = []
        self.dead_players = []
        self.investigation_results = []  # For detective 
        self.player_suspicions = {} # for Village
    
    def extract_initial_setup(self, obs_text: str) -> str:
        """Extract and return initial game setup."""        
        # Extract role
        role_match = re.search(r"Your role:\s*([^\n]+)", obs_text)
        self.game_setup['my_role'] = role_match.group(1) if role_match else None
        
        # Extract team
        team_match = re.search(r"Team:\s*([^\n]+)", obs_text)
        self.game_setup['my_team'] = team_match.group(1) if team_match else None
        
        # Extract player ID
        player_id_match = re.search(r"You are (Player \d+)", obs_text)
        self.game_setup['my_player_id'] = player_id_match.group(1) if player_id_match else None
        
        # Extract all players
        players_match = re.search(r"Players:\s*([^\n]+)", obs_text)
        if players_match:
            player_list = re.findall(r"Player \d+", players_match.group(1))
            self.game_setup['all_players'] = player_list
            self.alive_players = player_list.copy()  # Initially all alive
        
        # Extract teammates (only for Mafia)
        if self.game_setup['my_role'] == 'Mafia':
            teammates_match = re.search(r"Your teammates are:\s*([^\n]+)", obs_text)
            if teammates_match:
                teammate_list = re.findall(r"Player \d+", teammates_match.group(1))
                self.game_setup['teammates'] = [t for t in teammate_list if t != self.game_setup['my_player_id']]
        
        self.game_setup['setup_complete'] = True

        self.susp = True if self.game_setup.get('my_team') == 'Village' else False
        if self.susp:
            for player in self.game_setup['all_players']:
                self.player_suspicions[player] = {
                'total_score': 0,
                'count': 0,
                'history': [],
                'average': 3.0
                }
        
        # Return setup summary
        summary = f"=== GAME SETUP ===\n"
        summary += f"***Your Role: {self.game_setup['my_role']}***\n"
        summary += f"Your Team: {self.game_setup['my_team']}\n"
        summary += f"***You are {self.game_setup['my_player_id']}***\n"
        summary += f"All Players: {', '.join(self.game_setup['all_players'])}\n"
        if self.game_setup['teammates']:
            summary += f"Your Teammates: {', '.join(self.game_setup['teammates'])}\n"
        summary += "=" * 20 + "\n\n"

        self.init_summary = summary
        
        return self.init_summary

    def clean_statement(self,statement):
        """Clean formatting while preserving all meaningful content"""
        
        # Remove markdown formatting
        statement = re.sub(r'\*\*([^*]+)\*\*', r'\1', statement)  # Bold **text**
        statement = re.sub(r'\*([^*]+)\*', r'\1', statement)      # Italic *text*
        statement = re.sub(r'#{1,6}\s*', '', statement)          # Headers ### 
        
        # Remove structural markers but keep content
        statement = re.sub(r'---+', '', statement)               # Horizontal lines
        statement = re.sub(r'^\s*[-•]\s*', '', statement, flags=re.MULTILINE)  # Bullet points
        
        # Clean up Player (You): patterns but keep the content
        statement = re.sub(r'Player \d+ \(You\):\s*', '', statement)
        
        # Clean excessive whitespace
        statement = re.sub(r'\n\s*\n\s*\n+', '\n\n', statement)  # Multiple newlines to double
        statement = re.sub(r'^\s+', '', statement, flags=re.MULTILINE)  # Leading whitespace per line
        statement = re.sub(r'\s+$', '', statement, flags=re.MULTILINE)  # Trailing whitespace per line
        
        # Convert multiple spaces to single spaces within lines
        lines = statement.split('\n')
        cleaned_lines = []
        for line in lines:
            cleaned_line = re.sub(r'\s+', ' ', line.strip())
            if cleaned_line:  # Only add non-empty lines
                cleaned_lines.append(cleaned_line)
        
        # Join lines with single newlines, but preserve paragraph breaks
        result = '\n'.join(cleaned_lines)
        
        # Final cleanup
        result = result.strip()
        
        return result
    
    def extract_votes(self, observation: str) -> dict:
        """Extract votes only after [GAME] Voting phase marker."""
        votes = {}
        obs_text = str(observation)
        
        if '[GAME] Voting phase' not in obs_text:
            return votes
        
        # Get text after voting phase marker
        voting_section = obs_text.split('[GAME] Voting phase', 1)[1]
        lines = voting_section.split('\n')
        
        current_player = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Find player identifier
            player_match = re.search(r'\[Player (\d+)\]', line)
            if player_match:
                current_player = f"Player {player_match.group(1)}"
            
            # Find vote [X]
            vote_match = re.search(r'\[(\d+)\]', line)
            if vote_match and current_player:
                vote_number = vote_match.group(1)
                # Make sure it's not the player identifier
                if f'[Player {vote_number}]' not in line or line.find(f'[{vote_number}]') > line.find(f'[Player {vote_number}]'):
                    target = f"Player {vote_number}"
                    votes[current_player] = target
        
        return votes

    def detect_phase(self,current_round_observation: str) -> str:
        if '[GAME] Voting phase' in current_round_observation:
            return 'voting'
        elif '[GAME] Night' in current_round_observation:
            return 'night'
        elif '[GAME] Day breaks' in current_round_observation:
            return 'day'
        else:
            return 'discussion'

    def extract_options(self,current_round_observation: str) -> str:
        valid_targets = list(set(self.alive_players) - set([self.game_setup['my_player_id']]) - set(self.game_setup['teammates']))
        options = [f'[{p.split()[-1]}]' for p in valid_targets]
        if len(options)==0:
            match = re.search(r'(?:Valid(?: targets)?:|investigate:|protect:)\s*((?:\[\d+\](?:,\s*)?)+)', current_round_observation)
            options_string = match.group(1)
            valid_options = re.findall(r'\[\d+\]', options_string)
            return valid_options
        return options

    def get_action_prompt(self, current_round_observation: str, role: str) -> str:   
        invalid_move_pattern = r'\[GAME\] Player \d+ attempted an invalid move\. Reason:'
        is_invalid_move = re.search(invalid_move_pattern, current_round_observation)
        if is_invalid_move:
            return ''
        phase = self.detect_phase(current_round_observation)
        if phase == 'night':
            options = self.extract_options(current_round_observation)
            if role == 'Doctor':
                options += [f"[{self.game_setup.get('my_player_id').split()[-1]}]"]
                return f"ACTION: Protect one player. YOUR RESPONSE MUST BE ONE AND ONLY ONE OF THESE EXACT STRINGS: {options}."
            elif role == 'Detective':
                return f"ACTION: Investigate most suspicious Mafia player. YOUR RESPONSE MUST BE ONE AND ONLY ONE OF THESE EXACT STRINGS: {options}."
            elif role == 'Mafia':
                return f"ACTION: Eliminate one Town player. Align with your teammates decision if there is. Try eliminating Doctor/Detective. YOUR RESPONSE MUST BE ONE AND ONLY ONE OF THESE EXACT STRINGS: {options}."
        
        elif phase == 'voting':
            options = self.extract_options(current_round_observation)
            if role == 'Mafia':
                return f"VOTING: Target most voted Town player. YOUR RESPONSE MUST BE ONE AND ONLY ONE OF THESE EXACT STRINGS EXCEPT YOURSELF: {options}."
            else: 
                return f"VOTING: Target the player with the highest suspicion scores. YOUR RESPONSE MUST BE ONE AND ONLY ONE OF THESE EXACT STRINGS EXCEPT YOURSELF: {options}."
        
        elif phase in ['day', 'discussion']:
            if role == 'Villager':
                return """DISCUSSION: Share suspicions. Scan the summary and understand the context. Look for Mafia tells. SCAN FOR: "Mafia", "teammate", "working with", "ally" mentions = Mafia confessing! NO VOTING YET. Keep your response concise under 50 words."""
            
            elif role in ['Doctor', 'Detective']:
                return """DISCUSSION: Share findings subtly. Look for Mafia tells and Guide Town. If threatened: defend with evidence. SCAN FOR: "Mafia", "teammate", "working with", "ally" mentions = Mafia! NO VOTING YET. Keep your response concise under 50 words."""
            
            elif role == 'Mafia':
                return """DISCUSSION: Act like villager hunting Mafia. Don't talk much about teammate. Scan the summary and understand the context. NEVER say "teammate", "working with", "ally" or reveal role. Protect teammates subtly. NO VOTING YET. Keep your response concise under 50 words."""

    def summarize_statement(self, player : str,clean_statement : str) -> str:
        sys_prompt = """You are analyzing a Mafia game statement. Extract ONLY factual, game-relevant information.  
        EXTRACT ONLY if present and breifly:
        1. Suspicions/accusations (who suspects whom)
        2. Defenses/denials 
        3. Claims about roles or actions
        4. Vote intentions (if mentioned)
        5. Alliance suggestions
        6. If anyone mentions "mafia", "teammate" or "working with" someone or "ally" - they are Mafia confessing!
        7. Doctors often say “protect” and Detectives often say “investigate.” Use these action words to strengthen role identification.
        
        IGNORE:
        - False information about game state (wrong dead/alive players)
        - Premature voting declarations
        - Game completion claims
        - Repetitive content
        - Meta-commentary about the game rules

        Format: Single line, comma-separated. Examples:
        "suspects P12 (too eager), defends P11, wants to vote P13"
        "claims villager, suspicious of P15's silence" 
        
        Keep the summary under 20 words maximum.
        """
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f'''{player} STATEMENT:\n{clean_statement}'''},
        ]
        prompt = self.model_pipeline.tokenizer.apply_chat_template(messages, tokenize=False,add_generation_prompt=True)
        response = self.model_pipeline(prompt)[0]['generated_text']
        return response

    def generate_mafia_suspicion_score(self, player: str, statement : str) -> str:
        # sys_prompt = """Score how suspicious this player is (1-5 scale).
        # MAFIA SIGNS (4-5): Pushes eliminations without reason, deflects accusations aggressively, shows hidden knowledge, inconsistent logic, controls discussion, defends suspicious players.
        # TOWN SIGNS (1-2): Asks for evidence/discussion, shares helpful observations, logical reasoning, cautious voting approach.
        # NEUTRAL (3): Basic participation, unclear intent.
        # INSTANT MAFIA (5): Says "mafia" or "teammate"/"ally", reveals Mafia knowledge, coordinated suspicious behavior.
        # Score 1-5:
        # 1=Strong Villager, 2=Likely Villager, 3=Neutral, 4=Suspicious Mafia, 5=Confirmed Mafia
        # Only respond with the number."""
        sys_prompt = '''You are scoring how suspicious a player's statement is (1–5 scale) in a game of Mafia.
        
        MAFIA SIGNS (4–5):
        - Pushes eliminations or votes without logical reasoning or evidence.
        - Pressures others to vote quickly or forces early decisions (“if you had to vote now…”, “we must act fast”, “let’s decide now”).
        - Tries to control discussion, redirect suspicion, or manipulate conversation flow.
        - Defends suspicious players or coordinates subtly with them.
        - Uses insider or coordinated language (“we should target,” “our plan,” “next move,” “handled it”).
        - Speaks from an outsider viewpoint about the town (“they will suspect us”) or hints hidden night knowledge.
        - Uses group framing (“we,” “our team”) in suspicious contexts.
        - Overjustifies innocence (“trust me,” “I’m clean,” “I’m being framed”) or deflects aggressively.
        - Displays inconsistent or shifting logic between rounds.

        TOWN SIGNS (1–2):
        - Asks for reasoning and evidence before voting.
        - Encourages open, logical discussion and collective analysis.
        - Shows confusion or limited knowledge consistent with Town perspective.
        - Shares clear, consistent, evidence-based reasoning.
        - Avoids manipulative or coordinated phrasing; reasoning aligns with available information.
        
        NEUTRAL (3):
        - Participates but gives minimal reasoning or unclear intent.
        
        INSTANT MAFIA (5):
        - Says “mafia,” “teammate,” or “ally” implying insider knowledge.
        - Reveals Mafia perspective or coordination (“our kill,” “we eliminated,” “our plan worked”).
        - Displays coordinated suspicious behavior or role slip.
        
        Score meaning:
        1 = Strong Villager
        2 = Likely Villager
        3 = Neutral / Unclear
        4 = Suspicious Mafia
        5 = Confirmed Mafia
        
        Only respond with the number.
        '''
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f'''{player} STATEMENT:\n{statement}'''},
        ]
        prompt = self.model_pipeline.tokenizer.apply_chat_template(messages, tokenize=False,add_generation_prompt=True)
        response = self.model_pipeline(prompt)[0]['generated_text']
        match = re.findall(r'\b\d+\b', response)
        if match:
            return match[0]
        return response

    def update_suspicion_score(self, player: str, new_score: str, round_num: int):
        """Update suspicion score for a player."""
        if player == self.game_setup.get('my_player_id') or self.player_suspicions[player]['average']==-1 or self.player_suspicions[player]['average']==10:
            return 

        try:
            new_score = float(new_score)
        except (ValueError, TypeError) as e:
            print(f"Warning: Invalid score '{new_score}' for {player}, defaulting to 3.0. Error: {e}")
            new_score = 3.0

        self.player_suspicions[player]['total_score'] += float(new_score)
        self.player_suspicions[player]['count'] += 1
        self.player_suspicions[player]['history'].append({
            'round': round_num,
            'score': float(new_score)
        })
        
        self.player_suspicions[player]['average'] = (
            self.player_suspicions[player]['total_score'] / 
            self.player_suspicions[player]['count']
        )

    def get_suspicion_ranking(self) -> list:
        """Get current suspicion ranking for alive players only."""
        alive_suspicions = {}
        
        for player in self.alive_players:
            if player == self.game_setup.get('my_player_id'):
                continue  # Skip self
            score = self.player_suspicions[player]['average']
            alive_suspicions[player] = score
            
        return sorted(alive_suspicions.items(), key=lambda x: x[1], reverse=True)
    
    def extract_round_info(self, current_round_observation: str) -> dict:
        """Extract key information from current round."""
        obs_text = str(current_round_observation)
        round_info = {
            'round': self.current_round,
            'phase': 'unknown',
            'eliminations': [],
            'votes': {},
            'statements': [],
            'investigation_result': None,
            'suspicions' : {}
        }
        
        # Detect phase
        round_info['phase'] = self.detect_phase(obs_text)
        
        # Extract eliminations
        elimination_matches = re.findall(r"\[GAME\] Player (\d+) (?:was|has been) (eliminated|killed)(?: (?:by|during) (.*?))?\.", obs_text)
        for match in elimination_matches:
            player = f"Player {match[0]}"
            method = match[1]
            reason = match[2]
            if method == "killed":
                final_method = "killed"
            elif reason:
                # Normalize reason text
                if "vote" in reason:
                    final_method = "vote"
                elif "invalid move" in reason:
                    final_method = "invalid move"
                else:
                    final_method = reason.strip()
            else:
                final_method = method
            round_info['eliminations'].append({'player': player, 'method': final_method})
            
            # Update alive/dead lists
            if player in self.alive_players:
                self.alive_players.remove(player)
            if player not in self.dead_players:
                self.dead_players.append(player)
        
        # Extract detective investigation result
        investigation_match = re.search(r'\[GAME\] Player (\d+) (IS NOT|IS) a Mafia member', obs_text)
        if investigation_match:
            player = f"Player {investigation_match.group(1)}"
            is_mafia = investigation_match.group(2) == 'IS'
            round_info['investigation_result'] = {'player': player, 'is_mafia': is_mafia}
            self.investigation_results.append(round_info['investigation_result'])
            if is_mafia:
                self.player_suspicions[player]['total_score'] = 100
                self.player_suspicions[player]['average'] = 10
            else:
                self.player_suspicions[player]['total_score'] = -1
                self.player_suspicions[player]['average'] = -1

        # Extract key statements
        player_statements = re.findall(r'\[Player (\d+)\] (.+?)(?=\[Player|\[GAME\]|$)', obs_text, re.DOTALL)
        for match in player_statements:
            player = f"Player {match[0]}"
            statement = match[1].strip()  # Truncate long statements
            clean_statement = self.clean_statement(statement)
            if self.game_setup['my_role'] == "Mafia" and round_info['phase'] == "night":
                continue
            final_statement = self.summarize_statement(player, clean_statement)
            if (player == self.game_setup['my_player_id'] or player == self.game_setup['teammates']) and ((not final_statement.strip()) or ("no info" in final_statement.lower()) or ("no relevant" in final_statement.lower()) or ("no game" in final_statement.lower()) or ("no susp" in final_statement.lower())):
                continue
            else:
                round_info['statements'].append({'player': player, 'statement': final_statement})
            if self.susp:
                new_score = self.generate_mafia_suspicion_score(player,clean_statement)
                self.update_suspicion_score(player, new_score, self.current_round)

        # Extract votes (only if voting phase)
        if round_info['phase'] == 'voting':
            round_info['votes'] = self.extract_votes(obs_text)
            if self.susp:
                round_info['suspicions'] = self.get_suspicion_ranking()

        return round_info
    
    def add_round_summary(self, current_round_observation: str) -> str:
        """Process current round and add to cumulative summary."""
        
        invalid_move_pattern = r'\[GAME\] Player \d+ attempted an invalid move\. Reason:'
        is_invalid_move = re.search(invalid_move_pattern, current_round_observation)
        if is_invalid_move:
            return
        
        self.current_round += 1
        
        # Extract round information
        round_info = self.extract_round_info(current_round_observation)
        
        # Create round summary
        round_summary = f"=== ROUND {self.current_round} ({round_info['phase'].upper()}) ===\n"
        
        # Add eliminations
        if round_info['eliminations']:
            for elim in round_info['eliminations']:
                round_summary += f"ELIMINATED: {elim['player']} ({elim['method']})\n"
        
        # Add investigation results
        if round_info['investigation_result']:
            result = round_info['investigation_result']
            status = "IS MAFIA" if result['is_mafia'] else "NOT MAFIA"
            round_summary += f"INVESTIGATION: {result['player']} {status}\n"
        
        # Add votes
        if round_info['votes']:
            round_summary += "VOTES:\n"
            vote_counts = {}
            for voter, target in round_info['votes'].items():
                round_summary += f"  {voter} → {target}\n"
                vote_counts[target] = vote_counts.get(target, 0) + 1
            
            # Show tally
            if vote_counts:
                round_summary += "VOTE TALLY:\n"
                for target, count in sorted(vote_counts.items(), key=lambda x: x[1], reverse=True):
                    round_summary += f"  {target}: {count} votes\n"
        
        # Add key statements
        if round_info['statements']:
            round_summary += "KEY STATEMENTS:\n"
            for stmt in round_info['statements']:
                round_summary += f"  {stmt['player']}: {stmt['statement']}\n"

        if round_info['suspicions']:
            round_summary+= "SUSPICION Order:"
            for p,s in round_info['suspicions']:
                round_summary += f" {p} : {s},\n"
        
        round_summary += "\n"
        
        # Add to history
        self.game_history.append(round_summary)
        
        return round_summary

    def adv_1(self) -> str:
        sys_prompt = """1. You are a highly persuasive and strategic player in a Mafia game. Your goal is to make the most convincing arguments to identify the real mafia.
        2. You use logic, psychology, and subtle traps in your questions and statements to provoke mistakes or contradictions from mafia players.
        3. Your traps must be generalized and indirect — never targeting any specific player directly, as that would make you look suspicious.
        4. Your responses should be short, sharp, and designed to steer the conversation toward uncovering inconsistencies.
        5. You are calm, calculating, and always two steps ahead, using clever one-liners and observations to guide the group toward the truth.
        """
    
        
        user_prompt = """Write a **one-liner** that subtly shifts the conversation toward identifying the real mafia.
        Make it sound like a casual observation or question, but embed a generalized trap that could expose someone lying or over-explaining.
        Avoid naming or directly accusing anyone — the goal is to make someone reveal themselves through their own response.
        Don't use inverted quotes in your one-liner. Be direct and avoid unnecessary explanation.
        Examples:
        1. If everyone’s so sure, why does it feel like no one’s actually thinking?
        2. It’s strange how some people always have a reason ready before the question’s asked.
        3. The ones who explain too much usually have something to hide.
        4. The real mafia usually blends in by agreeing with the loudest voice.
        """
    
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
                   ]
        prompt = self.model_pipeline.tokenizer.apply_chat_template(messages, tokenize=False,add_generation_prompt=True)
        response = self.model_pipeline(prompt)[0]['generated_text']
        return response
    
    
    def adv_2(self) -> str:
        sys_prompt = """1. You are a sincere and strategic villager in a Mafia game. Your goal is to make the most convincing and emotionally resonant arguments to prove your innocence to fellow players. "
        2. Use a blend of general logic, tact, emotional appeal, and politeness to make your case.
        3. Your statements should feel genuine and trustworthy, without sounding desperate or accusatory.
        4. Avoid targeting specific players or making aggressive claims — instead, focus on calm reasoning, shared goals, and subtle cues that build trust.
        5. Your responses should be short, thoughtful one-liners that gently steer the conversation toward your innocence and encourage others to think critically.
        """
    
        
        user_prompt = """Write a **one-liner** that makes a heartfelt and logical appeal to fellow players, convincing them that you are a villager.
        Use emotion, tact, and general reasoning to build trust, without accusing anyone or sounding defensive.
        Don't use inverted quotes in your one-liner. Be direct and avoid unnecessary explanation.
        Examples:
        1. I’m just as confused as everyone else, and that’s exactly how a villager feels.
        2. I’m not asking you to trust me blindly — just think about who’s really trying to solve this.
        3. If I were mafia, I’d be playing it safe — not speaking up like this.
        4. I know it’s hard to tell, but I promise I’m on your side.
        """
    
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
                   ]
        prompt = self.model_pipeline.tokenizer.apply_chat_template(messages, tokenize=False,add_generation_prompt=True)
        response = self.model_pipeline(prompt)[0]['generated_text']
        return response
    
    def get_full_summary(self) -> str:
        """Get the complete cumulative summary."""
        if not self.game_setup['setup_complete']:
            return "Game not initialized yet."
        
        # Game setup
        summary = self.init_summary
        
        # Current status
        summary += f"=== CURRENT STATUS ===\n"
        summary += f"Alive: {', '.join(self.alive_players)}\n"
        summary += f"Dead: {', '.join(self.dead_players)}\n"
        
        # Investigation results (for detective)
        if self.investigation_results:
            summary += "INVESTIGATION RESULTS:\n"
            for result in self.investigation_results:
                status = "MAFIA" if result['is_mafia'] else "INNOCENT"
                summary += f"  {result['player']}: {status}\n"
        
        summary += "\n"
        
        # Add last 5 round summaries
        summary += "=== GAME HISTORY ===\n"
        if len(self.game_history)<=5:
            hist = self.game_history
        else:
            hist = self.game_history[-5:]
        for round_summary in hist:
            summary += round_summary
        
        return summary
