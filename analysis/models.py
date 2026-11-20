from django.db import models


class PositionAnalysis(models.Model):
    """Server Stockfish result for one position. Shared by all users. Scores are from the side to move's view."""

    fen = models.CharField(max_length=100, unique=True)  # normalised: board, side, castling, en passant
    depth = models.IntegerField()
    lines = models.JSONField(default=list)  # [{"uci": [...], "cp": int|None, "mate": int|None}], best first
    cp = models.IntegerField(null=True)  # best score in centipawns, None when it is a mate score
    mate = models.IntegerField(null=True)  # moves to mate for the side to move; 0 = side to move is mated
    engine_version = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def best_cp(self) -> int | None:
        return self.cp

    def mate_for_side_to_move(self) -> int | None:
        return self.mate


class MoveExplanation(models.Model):
    """Words for one move from one position, in one language. Shared by all users."""

    position = models.ForeignKey(PositionAnalysis, on_delete=models.CASCADE, related_name="explanations")
    move_uci = models.CharField(max_length=5)
    language = models.CharField(max_length=2)
    depth = models.CharField(max_length=5)  # "short" | "full"
    text = models.TextField()
    source = models.CharField(max_length=10)  # "template" | "ai"
    model = models.CharField(max_length=50, blank=True)
    needs_ai = models.BooleanField(default=False, db_index=True)  # template stand-in waiting for AI text
    facts = models.JSONField(default=dict)  # the FactPacket, so the AI text can be filled in later
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["position", "move_uci", "language", "depth"],
                                               name="unique_explanation")]
