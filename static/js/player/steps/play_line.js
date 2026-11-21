// Replay a line from memory: the learner plays one side, the app plays the other.
import {after, turnOf} from "../board.js"
import {localSan} from "../san.js"

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

export function playerIndexes(step) {
    const firstMover = turnOf(step.fen)
    return step.moves.map((_, i) => i).filter(i => (i % 2 === 0 ? firstMover : firstMover === "white" ? "black" : "white") === step.side)
}

export async function run(step, ctx) {
    const {board, ui, t, lang} = ctx
    const started = performance.now()
    const players = playerIndexes(step)
    const tries = players.map(() => [])
    const hints = players.map(() => 0)
    let current = -1
    let anyWrong = false

    await board.orient(step.side)
    await board.setFen(step.fen, false)
    ui.prompt(step.prompt)
    ui.hint(() => {
        if (current < 0) return
        hints[players.indexOf(current)] += 1
        ui.coach(step.hint)
        const move = step.moves[current]
        board.mark([move.slice(0, 2)], "hint")
    })

    let fen = step.fen
    const played = []
    for (let i = 0; i < step.moves.length; i++) {
        const main = step.moves[i]
        if (!players.includes(i)) {
            await sleep(400)
            const next = await board.play(fen, main)
            fen = next.fen
            played.push(localSan(next.san, lang))
            ui.chips(played)
            continue
        }
        current = i
        const k = players.indexOf(i)
        const accepted = new Set([main, ...((step.also_accept || {})[String(i)] || [])])
        let wrong = 0
        for (;;) {
            const forced = wrong >= 2 ? main : null
            if (forced) board.arrows([[main.slice(0, 2), main.slice(2, 4), "success"]])
            const uci = await board.waitForMove(fen, forced)
            tries[k].push(uci)
            if (accepted.has(uci)) {
                ctx.streak(tries[k].length === 1 && hints[k] === 0)
                if (uci !== main) {
                    ui.coach(t.alsoWorks)
                    await board.setFen(fen, false)
                    await sleep(300)
                    await board.play(fen, main)
                } else {
                    ui.coach("")
                }
                const next = after(fen, main)
                await board.setFen(next.fen, false)
                fen = next.fen
                played.push(localSan(next.san, lang))
                ui.chips(played)
                const note = (step.notes || {})[String(i)]
                if (note) ui.coach(note)
                break
            }
            wrong += 1
            anyWrong = true
            ctx.streak(false)
            ui.coach(wrong >= 2 ? t.showAnswer : t.notQuite)
            board.shake()
            await board.setFen(fen, true)
        }
        board.clear()
    }
    ui.hint(null)
    await ui.feedback({kind: anyWrong ? "neutral" : "ok", title: anyWrong ? t.lineDone : t.excellent})
    const alternatives = i => (step.also_accept || {})[String(i)] || []
    const correct = players.filter((i, k) => hints[k] === 0
        && (tries[k][0] === step.moves[i] || alternatives(i).includes(tries[k][0]))).length
    return {tries, hints, ms: Math.round(performance.now() - started), items: players.length, correct, requeue: anyWrong}
}
