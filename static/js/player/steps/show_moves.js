// A sequence plays out, one caption per move; the learner moves on with Continue.
import {localSan} from "../san.js"

export async function run(step, {board, ui, lang, orientation}) {
    const started = performance.now()
    await board.orient(orientation)
    await board.setFen(step.fen, false)
    if (step.text) {
        ui.coach(step.text)
        await ui.feedback({kind: "neutral"})
    }
    let fen = step.fen
    const played = []
    for (const item of step.moves) {
        const next = await board.play(fen, item.uci)
        fen = next.fen
        played.push(localSan(next.san, lang))
        ui.chips(played)
        board.arrows([[item.uci.slice(0, 2), item.uci.slice(2, 4), "info"]])
        ui.coach(item.caption)
        await ui.feedback({kind: "neutral"})
    }
    board.clear()
    return {tries: [], hints: 0, ms: Math.round(performance.now() - started), items: 0, correct: 0, requeue: false}
}
