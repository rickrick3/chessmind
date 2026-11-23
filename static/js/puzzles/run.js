// One puzzle on the board. The opponent's first move is played, then the learner finds the solution moves; any
// checkmating move solves it. `onDecided(body)` is called exactly once, at the first of: the line completed
// correctly, the first wrong move, the first hint (before the marker shows), or Show solution. After that the
// learner can keep going to learn the idea, but nothing is rated.
import {after} from "../player/board.js"
import {Chess} from "../../vendor/chess.js/chess.js"
import {localSan} from "../player/san.js"

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const SOLUTION = Symbol("solution")

const mates = fen => new Chess(fen).isCheckmate()

export async function runPuzzle(puzzle, ctx) {
    const {board, ui, t, lang, onDecided} = ctx
    const started = performance.now()
    const moves = puzzle.moves
    const played = []
    let hints = 0
    let decided = false
    let clean = true
    let hintLevel = 0
    let i = 1
    let askSolution
    const solutionAsked = new Promise(resolve => { askSolution = resolve })

    const decide = solutionShown => {
        if (decided) return
        decided = true
        if (onDecided) {
            onDecided({played: [...played], hints, solution_shown: solutionShown,
                       ms: Math.round(performance.now() - started)})
        }
    }

    ui.reset()
    await board.orient(puzzle.side)
    await board.setFen(puzzle.fen, false)
    ui.prompt(puzzle.side === "white" ? t.whiteToPlay : t.blackToPlay)
    await sleep(500)
    let fen = (await board.play(puzzle.fen, moves[0])).fen
    const chips = [localSan(after(puzzle.fen, moves[0]).san, lang)]
    ui.chips(chips)

    ui.onHint(() => {
        if (i >= moves.length) return
        clean = false
        if (!decided) hints += 1
        decide(false)
        hintLevel += 1
        const move = moves[i]
        if (hintLevel === 1) board.mark([move.slice(0, 2)], "hint")
        else board.arrows([[move.slice(0, 2), move.slice(2, 4), "info"]])
    })
    ui.onSolution(() => {
        clean = false
        decide(true)
        askSolution(SOLUTION)
    })

    let wrong = 0
    while (i < moves.length) {
        const forced = wrong >= 2 ? moves[i] : null
        if (forced) board.arrows([[forced.slice(0, 2), forced.slice(2, 4), "success"]])
        const got = await Promise.race([board.waitForMove(fen, forced), solutionAsked])
        if (got === SOLUTION) {
            board.clear()
            await board.setFen(fen, false)
            for (; i < moves.length; i++) {
                await sleep(600)
                const next = await board.play(fen, moves[i])
                fen = next.fen
                chips.push(localSan(next.san, lang))
                ui.chips(chips)
            }
            break
        }
        const next = after(fen, got)
        const mate = mates(next.fen)
        if (got === moves[i] || mate) {
            if (!decided) played.push(got)
            board.clear()
            ui.coach(got !== moves[i] ? t.alsoMates : "")
            await board.setFen(next.fen, false)
            fen = next.fen
            chips.push(localSan(next.san, lang))
            ui.chips(chips)
            if (mate || i === moves.length - 1) {
                decide(false)
                break
            }
            await sleep(400)
            const reply = await board.play(fen, moves[i + 1])
            fen = reply.fen
            chips.push(localSan(reply.san, lang))
            ui.chips(chips)
            i += 2
            wrong = 0
            hintLevel = 0
            continue
        }
        clean = false
        if (!decided) played.push(got)
        decide(false)
        wrong += 1
        ui.coach(wrong >= 2 ? t.showAnswer : t.missed)
        board.shake()
        await board.setFen(fen, true)
    }
    ui.onHint(null)
    ui.onSolution(null)
    return {solved: clean}
}
