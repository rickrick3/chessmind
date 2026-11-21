// Find the move. Two wrong tries and the answer is shown; the learner then plays it.
import {after, turnOf} from "../board.js"

export async function run(step, ctx) {
    const {board, ui, t} = ctx
    const started = performance.now()
    const tries = []
    let hints = 0
    const goods = step.also_good || []
    const right = new Set([...step.accept, ...goods.map(g => g.uci)])
    const answer = step.accept[0]

    await board.orient(turnOf(step.fen))
    await board.setFen(step.fen, false)
    board.arrows((step.arrows || []).map(([from, to]) => [from, to, "info"]))
    ui.prompt(step.prompt)
    ui.hint(() => {
        hints += 1
        ui.coach(step.hint)
        board.mark([answer.slice(0, 2)], "hint")
    })

    let wrong = 0
    for (;;) {
        const forced = wrong >= 2 ? answer : null
        if (forced) board.arrows([[answer.slice(0, 2), answer.slice(2, 4), "success"]])
        const uci = await board.waitForMove(step.fen, forced)
        tries.push(uci)
        if (right.has(uci)) {
            ctx.streak(tries.length === 1 && hints === 0)
            const good = goods.find(g => g.uci === uci)
            if (good && !step.accept.includes(uci)) {
                await board.setFen(step.fen, false)
                await board.play(step.fen, answer)
            } else {
                await board.setFen(after(step.fen, uci).fen, false)
            }
            ui.hint(null)
            await ui.feedback({kind: "ok", title: t.excellent, text: good && !step.accept.includes(uci) ? good.note : step.correct})
            break
        }
        wrong += 1
        ctx.streak(false)
        const known = (step.wrong || []).find(w => w.uci === uci)
        board.shake()
        await ui.feedback({kind: "bad", title: t.notQuite, text: known ? known.feedback : wrong >= 2 ? t.showAnswer : t.tryAgain})
        await board.setFen(step.fen, true)
    }
    board.clear()
    const firstRight = right.has(tries[0]) && hints === 0
    return {tries, hints, ms: Math.round(performance.now() - started), items: 1, correct: firstRight ? 1 : 0,
            requeue: !right.has(tries[0])}
}
