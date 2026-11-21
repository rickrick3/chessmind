// The coach explains a position. Nothing to answer.
export async function run(step, {board, ui, orientation}) {
    const started = performance.now()
    await board.orient(orientation)
    await board.setFen(step.fen, false)
    board.arrows((step.arrows || []).map(([from, to]) => [from, to, "info"]))
    board.mark(step.highlights || [])
    ui.coach(step.text)
    await ui.feedback({kind: "neutral"})
    board.clear()
    return {tries: [], hints: 0, ms: Math.round(performance.now() - started), items: 0, correct: 0, requeue: false}
}
