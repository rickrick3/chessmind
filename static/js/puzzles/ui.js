// Everything on the puzzle screen except the board. Text is always set with textContent.
export function createUi(root, t) {
    const $ = selector => root.querySelector(selector)
    const els = {
        start: $(".pz-start"), play: $(".pz-play"), prompt: $(".pz-prompt"), coach: $(".pz-coach"),
        coachRow: $(".pz-coach-row"), hint: $(".pz-hint"), solution: $(".pz-solution"), actions: $(".pz-actions"),
        result: $(".pz-result"), error: $(".pz-error"),
    }
    let onHint = null
    let onSolution = null
    els.hint.addEventListener("click", () => onHint && onHint())
    els.solution.addEventListener("click", () => onSolution && onSolution())

    const el = (tag, className, text) => {
        const node = document.createElement(tag)
        if (className) node.className = className
        if (text !== undefined) node.textContent = text
        return node
    }
    let chipsBox = null

    const api = {
        el,
        showBoard() {
            if (els.start) els.start.hidden = true
            els.play.hidden = false
        },
        showStart() {
            els.play.hidden = true
            if (els.start) els.start.hidden = false
        },
        reset() {
            api.prompt("")
            api.coach("")
            api.chips([])
            els.result.hidden = true
            els.result.replaceChildren()
            els.actions.hidden = false
            api.onHint(null)
            api.onSolution(null)
        },
        prompt(text) { els.prompt.textContent = text || ""; els.prompt.hidden = !text },
        coach(text) { els.coach.textContent = text || ""; els.coachRow.hidden = !text },
        chips(list) {
            if (!chipsBox) {
                chipsBox = el("div", "pz-chips-moves")
                els.prompt.after(chipsBox)
            }
            chipsBox.replaceChildren(...list.map((san, i) => el("span", i === list.length - 1 ? "pz-move is-new" : "pz-move", san)))
        },
        onHint(handler) { onHint = handler; (els.hint.closest(".pz-hint-wrap") || els.hint).hidden = !handler },
        onSolution(handler) { onSolution = handler; els.solution.hidden = !handler },
        error(message) { els.error.textContent = message; els.error.hidden = false },
        clearError() { els.error.textContent = ""; els.error.hidden = true },
        // The result card; resolves when the learner asks for the next puzzle.
        result(box) {
            els.actions.hidden = true
            els.result.replaceChildren(...box)
            els.result.hidden = false
        },
    }
    return api
}
