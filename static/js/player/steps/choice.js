// Pick one answer. Two wrong picks and the right one is shown; the learner then picks it.
import {after} from "../board.js"
import {localSan} from "../san.js"

export async function run(step, ctx) {
    const {board, ui, t, lang, orientation} = ctx
    const started = performance.now()
    const tries = []
    let hints = 0
    await board.orient(orientation)
    await board.setFen(step.fen, false)
    ui.prompt(step.question)
    ui.renderOptions(step.options.map(o => ("text" in o ? o.text : localSan(after(step.fen, o.uci).san, lang))))
    ui.hint(() => {
        hints += 1
        ui.coach(step.hint)
    })

    let wrong = 0
    for (;;) {
        const only = wrong >= 2 ? step.answer : null
        if (only !== null) ui.markOption(step.answer, "answer")
        const picked = await ui.pickOption(only)
        tries.push(picked)
        if (picked === step.answer) {
            ctx.streak(tries.length === 1 && hints === 0)
            ui.markOption(picked, "ok")
            ui.hint(null)
            await ui.feedback({kind: "ok", title: t.excellent, text: step.explanation})
            break
        }
        wrong += 1
        ctx.streak(false)
        ui.markOption(picked, "bad")
        await ui.feedback({kind: "bad", title: t.notQuite, text: wrong >= 2 ? t.showAnswer : t.tryAgain})
    }
    const firstRight = tries[0] === step.answer && hints === 0
    return {tries, hints, ms: Math.round(performance.now() - started), items: 1, correct: firstRight ? 1 : 0,
            requeue: tries[0] !== step.answer}
}
