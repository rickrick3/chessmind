"""Chess facts the beginner course states, pinned after the final review."""
import json
from pathlib import Path

import chess

SEED = Path(__file__).parent.parent / "curriculum" / "seed" / "beginner.json"


def steps():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    for unit in data["courses"][0]["units"]:
        for les in unit["lessons"]:
            for s in les["content"]["steps"]:
                yield les["slug"], s


def step(slug, sid):
    return next(s for les, s in steps() if les == slug and s["id"] == sid)


def test_ladder_checks_leave_the_king_only_moves_up():
    s = step("ladder-mate", "ladder")
    board = chess.Board(s["fen"])
    for item in s["moves"]:
        move = chess.Move.from_uci(item["uci"])
        if board.turn == chess.BLACK:
            here = chess.square_rank(board.king(chess.BLACK))
            assert all(chess.square_rank(m.to_square) > here for m in board.legal_moves), item["uci"]
        board.push(move)
    assert board.is_checkmate()


def test_stalemate_trap_names_one_stalemate_and_it_is_one():
    s = step("queen-king-mate", "stalemate-trap")
    board = chess.Board(s["fen"])
    stalemates = 0
    for o in s["options"]:
        b = board.copy()
        b.push_uci(o["uci"])
        stalemates += b.is_stalemate()
    assert stalemates == 1 and "two" not in s["question"]["en"].lower()


def test_mate_in_two_question_asks_for_the_fastest_mate():
    assert "in two" in step("mate-in-two", "first-move")["question"]["en"]


def test_material_counts_are_right():
    assert "pawn up" not in step("free-pieces", "win-pawn")["notes"]["2"]["en"]
    correct = step("saving-a-piece", "take-attacker")["correct"]
    assert "knight up" not in correct["en"] and "de plus" not in correct["fr"]


def test_a_centre_pawn_does_not_attack_two_centre_squares():
    assert "two central squares" not in step("take-the-centre", "why")["explanation"]["en"]


def test_the_square_is_described_correctly():
    assert "four squares wide" not in step("square-rule", "inside")["hint"]["en"]


def test_choice_questions_have_one_right_answer():
    assert "knight or bishop" in step("develop", "best-develop")["question"]["en"]
    assert "safe" not in step("active-king", "hunt")["question"]["en"]


def test_play_lines_accept_the_other_mates_in_two():
    assert "b1b7" in step("ladder-mate", "two-moves")["also_accept"]["0"]
    s = step("rook-king-mate", "waiting")
    board = chess.Board(s["fen"])
    board.push_uci(s["moves"][0])
    assert [board.san(m) for m in board.legal_moves] == ["Kc8"]  # the reply is forced, not a blunder


def test_no_find_move_hangs_on_the_grading_threshold():
    for slug, s in steps():
        if s["type"] != "find_move":
            continue
        board = chess.Board(s["fen"])
        assert board.legal_moves.count() > 1, (slug, s["id"])  # a single legal move teaches nothing
        promotions = [u for u in s["accept"] + [g["uci"] for g in s.get("also_good", [])] if len(u) == 5]
        assert all(u.endswith("q") for u in promotions), (slug, s["id"])


def test_french_says_forcing_not_forced():
    texts = json.dumps([s for les, s in steps() if les == "mate-in-two"], ensure_ascii=False)
    meta = json.dumps(json.loads(SEED.read_text(encoding="utf-8"))["courses"][0]["units"][3]["lessons"][4]["content"]["meta"],
                      ensure_ascii=False)
    # "coup forcé" means a forced move; a forcing move is "coup forçant". ("Rxg8 : forcé." is right: it is forced.)
    assert "coup forcé" not in texts + meta and "coups forcés" not in texts + meta
