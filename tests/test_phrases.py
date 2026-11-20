from analysis.phrases import template_text


def test_short_en_mentions_move(packet_good):
    t = template_text(packet_good, "en", "short")
    assert "Nf3" in t and "good move" in t


def test_short_fr_is_french(packet_good):
    assert "bon coup" in template_text(packet_good, "fr", "short")


def test_full_fr_names_better_move_and_replies(packet_blunder):
    t = template_text(packet_blunder, "fr", "full")
    assert packet_blunder.best_san in t and "Mieux" in t
    assert all(r in t for r in packet_blunder.replies_san)
    assert "gaffe" in t


def test_hanging_piece_sentence_en(packet_hanging_queen):
    assert "queen on d5" in template_text(packet_hanging_queen, "en", "full")


def test_hanging_piece_translated_fr(packet_hanging_queen):
    assert "dame en d5" in template_text(packet_hanging_queen, "fr", "full")


def test_full_en_mentions_winning_chances(packet_blunder):
    t = template_text(packet_blunder, "en", "full")
    assert "50%" in t and "12%" in t


def test_check_and_capture_mentioned_short(packet_good):
    from dataclasses import replace

    t = template_text(replace(packet_good, san="Bxf7+", is_check=True, captured="pawn"), "en", "short")
    assert "check" in t and "pawn" in t


def test_articles_and_gender(packet_blunder):
    from dataclasses import replace

    assert "the queen on d5" in template_text(packet_blunder, "en", "full")
    assert "la dame en d5" in template_text(packet_blunder, "fr", "full")
    assert "prend une tour" in template_text(replace(packet_blunder, captured="rook"), "fr", "short")
    assert "prend un fou" in template_text(replace(packet_blunder, captured="bishop"), "fr", "short")
