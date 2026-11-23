// The puzzle page: ask the server for the next puzzle, play it, send the outcome the moment it is decided,
// show the server's result, repeat.
import {createBoard} from "../player/board.js"
import {runPuzzle} from "./run.js"
import {createUi} from "./ui.js"

const PENDING = "chessmind:pending-puzzle:"
const DIFFICULTY = "chessmind:puzzle-difficulty"
const cfg = JSON.parse(document.getElementById("puzzle-config").textContent)
const t = cfg.i18n
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

function storage() {
    try { return window.localStorage } catch (e) { return null }
}

async function post(url, body, keepalive = false) {
    const r = await fetch(url, {
        method: "POST", credentials: "same-origin", keepalive,
        headers: {"Content-Type": "application/json", "X-CSRFToken": cfg.csrfToken},
        body: JSON.stringify(body),
    })
    let data = null
    try { data = await r.json() } catch (e) { /* empty body */ }
    return {ok: r.ok, status: r.status, data}
}

function forget(key) {
    try { storage()?.removeItem(key) } catch (e) { /* private mode */ }
}

// Send every outcome kept from an earlier visit or a dropped connection. True when none is left unsent.
async function resendPending() {
    const store = storage()
    if (!store) return true
    let keys = []
    try { keys = Object.keys(store).filter(k => k.startsWith(PENDING)) } catch (e) { return true }
    let left = 0
    for (const key of keys) {
        try {
            const body = JSON.parse(store.getItem(key))
            const r = await post(cfg.finishUrl.replace("{id}", key.slice(PENDING.length)), body, true)
            if (r.ok || (r.status >= 400 && r.status < 500)) forget(key)
            else left += 1
        } catch (e) { left += 1 /* still offline: keep it for next time */ }
    }
    return left === 0
}

async function finish(attemptId, body) {
    // Kept on the device before the first send, so closing the tab or losing the network never drops a miss.
    // Up to 3 retries (1 s, 3 s, 9 s); after that it stays kept and goes out before the next puzzle or visit.
    const key = PENDING + attemptId
    try { storage()?.setItem(key, JSON.stringify(body)) } catch (e) { /* private mode */ }
    const url = cfg.finishUrl.replace("{id}", attemptId)
    for (const wait of [0, 1000, 3000, 9000]) {
        if (wait) await sleep(wait)
        try {
            const r = await post(url, body, true)
            if (r.ok) { forget(key); return r.data }
            if (r.status >= 400 && r.status < 500) {
                forget(key)
                return {rejected: r.data?.error?.message || t.notSaved}
            }
        } catch (e) { /* network error: retry */ }
    }
    return {offline: true}
}

function difficulty() {
    try { return storage()?.getItem(DIFFICULTY) || "normal" } catch (e) { return "normal" }
}

function setupDifficulty(root) {
    const buttons = [...root.querySelectorAll("[data-difficulty]")]
    const mark = value => buttons.forEach(b => {
        b.classList.toggle("is-active", b.dataset.difficulty === value)
        b.setAttribute("aria-pressed", String(b.dataset.difficulty === value))
    })
    mark(difficulty())
    buttons.forEach(b => b.addEventListener("click", () => {
        try { storage()?.setItem(DIFFICULTY, b.dataset.difficulty) } catch (e) { /* per-viewer convenience only */ }
        mark(b.dataset.difficulty)
    }))
}

function resultCard(ui, result, localSolved) {
    const {el} = ui
    const box = []
    if (result.rejected || result.offline) {
        box.push(el("h2", "pz-result__title", localSolved ? t.solved : t.notSolved))
        box.push(el("p", "pz-result__note", result.rejected || t.savedLater))
        return box
    }
    box.push(el("h2", `pz-result__title ${result.solved ? "is-ok" : "is-bad"}`, result.solved ? t.solved : t.notSolved))
    const r = result.rating
    const change = r.change > 0 ? `+${r.change}` : String(r.change)
    const line = el("p", "pz-result__rating")
    line.append(el("strong", "pz-result__change", change), " · ",
                `${t.yourRating} ${t.about.replace("{low}", r.low).replace("{high}", r.high)}`)
    if (r.settling) line.append(` · ${t.settling}`)
    box.push(line)
    if (result.xp && result.xp.awarded) box.push(el("div", "pz-result__xp", `+${result.xp.awarded} XP`))
    const meta = el("p", "pz-result__meta", `${t.puzzleRating} ${result.puzzle.rating}`)
    box.push(meta)
    const themes = el("div", "pz-chips")
    for (const theme of result.puzzle.themes) themes.append(el("span", "pz-chip is-static", theme.label))
    box.push(themes)
    if (result.puzzle.game_url) {
        const game = el("a", "pz-result__game", t.viewGame)
        game.href = result.puzzle.game_url
        game.target = "_blank"
        game.rel = "noopener"
        box.push(game)
    }
    return box
}

function reportControls(ui, puzzleId) {
    const {el} = ui
    const wrap = el("div", "pz-report")
    const open = el("button", "cm-btn cm-btn--secondary cm-btn--sm", t.report)
    open.type = "button"
    open.addEventListener("click", () => {
        const choices = el("div", "pz-report__choices")
        for (const [reason, label] of [["wrong_solution", t.reportWrong], ["other", t.reportOther]]) {
            const b = el("button", "cm-btn cm-btn--secondary cm-btn--sm", label)
            b.type = "button"
            b.addEventListener("click", async () => {
                await post(cfg.reportUrl.replace("{id}", encodeURIComponent(puzzleId)), {reason}).catch(() => null)
                wrap.replaceChildren(el("p", "pz-report__done", t.reported))
            })
            choices.append(b)
        }
        wrap.replaceChildren(choices)
    })
    wrap.append(open)
    return wrap
}

const clicked = button => new Promise(resolve => button.addEventListener("click", resolve, {once: true}))

async function main() {
    const root = document.getElementById("puzzles")
    const ui = createUi(root, t)
    setupDifficulty(root)
    const go = root.querySelector(".pz-go")
    let board = null
    let timezone = "UTC"
    try { timezone = Intl.DateTimeFormat().resolvedOptions().timeZone } catch (e) { /* keep UTC */ }
    const sent = resendPending()

    for (;;) {  // the start panel; a session that runs out of puzzles comes back here
        await clicked(go)
        ui.clearError()
        ui.showBoard()
        board ||= createBoard(document.getElementById("board"), {orientation: "white", assetsUrl: cfg.assets, lang: cfg.lang})
        await sent
        let next = null
        for (;;) {
            // Never ask for a new puzzle while an earlier outcome is unsent: the server would serve that puzzle
            // again, and the learner would already know its answer.
            if (!(await resendPending())) {
                ui.error(t.stillOffline)
                if (!next) { ui.showStart(); break }
                await clicked(next)
                continue
            }
            ui.clearError()
            const r = await post(cfg.nextUrl, {mode: cfg.mode, theme: cfg.theme, difficulty: difficulty(), timezone})
                .catch(() => null)
            if (r && r.status === 404 && r.data?.error?.code === "no_puzzle") {
                ui.showStart()
                ui.error(r.data.error.message)
                break
            }
            if (!r || !r.ok) {
                ui.error(r?.data?.error?.message || t.loadError)
                if (!next) { ui.showStart(); break }
                await clicked(next)
                continue
            }
            const attemptId = r.data.attempt_id
            let outcome = null
            const {solved} = await runPuzzle(r.data.puzzle, {
                board, ui, t, lang: cfg.lang,
                onDecided: body => { outcome = finish(attemptId, body) },
            })
            const result = outcome ? await outcome : {offline: true}
            const box = resultCard(ui, result, solved)
            next = ui.el("button", "cm-btn cm-btn--primary pz-next", t.next)
            next.type = "button"
            const actions = ui.el("div", "pz-result__actions")
            actions.append(next)
            if (result.puzzle) actions.append(reportControls(ui, result.puzzle.id))
            box.push(actions)
            ui.result(box)
            next.focus({preventScroll: true})
            await clicked(next)
        }
    }
}

main()
