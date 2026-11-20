import {Chessboard, COLOR, FEN} from "../vendor/cm-chessboard/src/Chessboard.js"
import {Arrows, ARROW_TYPE} from "../vendor/cm-chessboard/src/extensions/arrows/Arrows.js"
import {Chess} from "../vendor/chess.js/chess.js"

const cfg = JSON.parse(document.getElementById("review-data").textContent)
const t = cfg.i18n
const board = new Chessboard(document.getElementById("board"), {
    position: FEN.start, assetsUrl: cfg.assets,
    orientation: cfg.orientation === "b" ? COLOR.black : COLOR.white,
    extensions: [{class: Arrows}],
})
let moves = []
let current = -1

const sq = uci => [uci.slice(0, 2), uci.slice(2, 4)]
const esc = s => $("<div>").text(s).html()

function show(i) {
    if (i < 0 || i >= moves.length) return
    current = i
    const m = moves[i]
    const game = new Chess(m.fen_before)
    board.removeArrows()
    board.setPosition(m.fen_before, false)
    const played = game.move(m.san)
    board.setPosition(game.fen(), true)
    board.addArrow(ARROW_TYPE.info, played.from, played.to)
    let html = `<div class="fw-semibold mb-1">${Math.ceil(m.ply / 2)}${m.ply % 2 ? "." : "…"} ${esc(m.san)}
        <span class="badge text-bg-light border">${esc(t.grades[m.grade])}</span></div><p class="mb-2">${esc(m.text)}</p>`
    if (m.key_moment && m.best_uci) {
        const [f, to] = sq(m.best_uci)
        board.addArrow(ARROW_TYPE.success, f, to)
        html += `<div class="small text-success mb-1">${esc(t.better)}: ${esc(new Chess(m.fen_before).move(m.best_uci).san)}</div>`
    }
    if (m.key_moment && m.replies_uci.length) {
        const after = new Chess(game.fen())
        const links = m.replies_uci.map(u => `<a class="reply" data-uci="${u}">${esc(new Chess(after.fen()).move(u).san)}</a>`)
        html += `<div class="small">${esc(t.replies)}: ${links.join(", ")}</div>`
    }
    $("#explain").html(html)
    $(".mv").removeClass("active")
    $(`.mv[data-i=${i}]`).addClass("active")[0]?.scrollIntoView({block: "nearest"})
}

$("#explain").on("click", ".reply", function () {
    const m = moves[current]
    const g = new Chess(m.fen_before)
    g.move(m.san)
    const r = g.move($(this).data("uci"))
    board.removeArrows()
    board.setPosition(g.fen(), true)
    board.addArrow(ARROW_TYPE.danger, r.from, r.to)
})

function render(data) {
    moves = data.moves
    $("#state").hide()
    $("#counts").text(Object.entries(data.counts).map(([g, n]) => `${t.grades[g]}: ${n}`).join(" · "))
    $("#moves").html(moves.map((m, i) =>
        `${m.ply % 2 ? `<span class="text-secondary small">${Math.ceil(m.ply / 2)}.</span>` : ""}` +
        `<span class="mv g-${m.grade}" data-i="${i}">${esc(m.san)}</span>`).join(" "))
    show(0)
}

$("#moves").on("click", ".mv", function () { show(Number($(this).data("i"))) })
$("#prev").on("click", () => show(current - 1))
$("#next").on("click", () => show(current + 1))
$(document).on("keydown", e => {
    if (e.key === "ArrowLeft") show(current - 1)
    if (e.key === "ArrowRight") show(current + 1)
})

function poll() {
    $.getJSON(cfg.statusUrl).done(data => {
        if (data.status === "done") render(data)
        else if (data.status === "failed") $("#state").text(t.failed)
        else setTimeout(poll, 3000)
    }).fail(() => setTimeout(poll, 5000))
}
poll()
