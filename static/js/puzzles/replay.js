// Replay a puzzle the learner has already seen. Nothing is sent to the server, so nothing is rated.
import {createBoard} from "../player/board.js"
import {runPuzzle} from "./run.js"
import {createUi} from "./ui.js"

const cfg = JSON.parse(document.getElementById("puzzle-config").textContent)
const t = cfg.i18n

async function main() {
    const root = document.getElementById("puzzles")
    const ui = createUi(root, t)
    const board = createBoard(document.getElementById("board"), {orientation: cfg.puzzle.side, assetsUrl: cfg.assets, lang: cfg.lang})
    const {solved} = await runPuzzle(cfg.puzzle, {board, ui, t, lang: cfg.lang, onDecided: null})
    ui.result([ui.el("h2", "pz-result__title", solved ? t.solved : t.notSolved), ui.el("p", "pz-result__note", t.replayDone)])
}

main()
