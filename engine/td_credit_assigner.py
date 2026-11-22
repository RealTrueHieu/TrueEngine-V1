import math
import json
import os

class TDLambdaCreditAssigner:
    """
    Temporal Difference Credit Assigner using TD(lambda) with gamma = 0.85
    to distribute blame/credit to chess moves leading up to a defeat or victory
    for TrueEngine V1.
    """
    def __init__(self, gamma=0.85, lambd=0.7, learning_rate=0.1):
        self.gamma = gamma          # Discount factor (0.85 as specified)
        self.lambd = lambd          # Eligibility trace decay parameter
        self.alpha = learning_rate  # Weight update learning rate
        self.trajectory = []        # List of dicts: {'fen': ..., 'move': ..., 'eval': ...}

    def reset(self):
        """Reset trajectory at the start of a new game."""
        self.trajectory = []

    def record_step(self, fen: str, move: str, evaluation: float):
        """
        Record a state (FEN), move made, and static/MCTS evaluation at step t.
        evaluation is expected in centipawns or win-probability [-1.0, 1.0].
        """
        self.trajectory.append({
            "fen": fen,
            "move": move,
            "eval": evaluation
        })

    def compute_blame_attribution(self, final_outcome: float):
        """
        Compute TD(lambda) blame attribution upon game termination.
        final_outcome: -1.0 for defeat, +1.0 for win, 0.0 for draw.
        
        Returns a list of tuples: (fen, move, blame_delta)
        """
        if not self.trajectory:
            return []

        T = len(self.trajectory)
        blames = [0.0] * T
        eligibility_traces = [0.0] * T

        # Convert evaluations to value range [-1, 1] using tanh scaling if in centipawns
        values = []
        for step in self.trajectory:
            cp = step["eval"]
            # Normalize centipawns to [-1, 1] using tanh(cp / 400)
            val = math.tanh(cp / 400.0)
            values.append(val)

        # Append terminal value
        values.append(final_outcome)

        # Backward TD(lambda) pass
        # Eligibility trace accumulation and TD error backpropagation
        e = 0.0
        for t in range(T - 1, -1, -1):
            # R_t is 0 for non-terminal transitions, final_outcome at terminal step T-1
            reward = final_outcome if t == T - 1 else 0.0
            next_val = values[t + 1]
            curr_val = values[t]

            # TD error delta_t = R_t + gamma * V(S_{t+1}) - V(S_t)
            td_error = reward + self.gamma * next_val - curr_val

            # Update eligibility trace: e_t = gamma * lambda * e_{t-1} + 1
            e = self.gamma * self.lambd * e + 1.0
            eligibility_traces[t] = e

            # Blame / credit update proportional to td_error * eligibility_trace
            # For defeat (final_outcome = -1.0), negative td_errors assign blame.
            blames[t] = td_error * e

        results = []
        for t in range(T):
            step = self.trajectory[t]
            results.append({
                "fen": step["fen"],
                "move": step["move"],
                "blame": blames[t],
                "td_error": blames[t] / (eligibility_traces[t] if eligibility_traces[t] > 0 else 1.0)
            })

        return results

    def update_book_weights(self, attribution_results, book_path: str):
        """
        Penalize losing moves in the opening book or experience memory using computed blame.
        """
        if not os.path.exists(book_path):
            return

        try:
            with open(book_path, "r", encoding="utf-8") as f:
                book = json.load(f)
        except Exception:
            return

        updated = False
        for res in attribution_results:
            fen = res["fen"]
            move = res["move"]
            blame = res["blame"] # Negative for defeat blame

            if fen in book and move in book[fen]:
                # Decrease weight for blamed moves (blame is negative on defeat)
                current_weight = book[fen][move].get("weight", 1.0)
                # Apply multiplicative penalty based on blame magnitude
                penalty = math.exp(self.alpha * blame) # blame is negative -> penalty < 1.0
                new_weight = max(0.01, current_weight * penalty)
                book[fen][move]["weight"] = new_weight
                updated = True

        if updated:
            try:
                with open(book_path, "w", encoding="utf-8") as f:
                    json.dump(book, f, indent=2)
            except Exception:
                pass
