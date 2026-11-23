// The lesson player: fetch the lesson, run its steps, send every try to the server, show the summary.
import {createBoard} from "./board.js"
import {StepQueue} from "./queue.js"
import {createUi} from "./ui.js"
import * as choice from "./steps/choice.js"
import * as explain from "./steps/explain.js"
import * as findMove from "./steps/find_move.js"
import * as playLine from "./steps/play_line.js"
import * as showMoves from "./steps/show_moves.js"

const RUNNERS = {explain: explain.run, show_moves: showMoves.run, find_move: findMove.run, choice: choice.run,
                 play_line: playLine.run}
const PENDING = "chessmind:pending:"
const cfg = JSON.parse(document.getElementById("player-config").textContent)
const t = cfg.i18n
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

function storage() {
    try { return window.localStorage } catch (e) { return null }
}

async function post(url, body) {
    const r = await fetch(url, {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": cfg.csrfToken},
        body: JSON.stringify(body),
    })
    let data = null
    try { data = await r.json() } catch (e) { /* empty body */ }
    return {ok: r.ok, status: r.status, data}
}

async function resendPending() {
    const store = storage()
    if (!store) return
    let keys = []
    try { keys = Object.keys(store).filter(k => k.startsWith(PENDING)) } catch (e) { return }
    for (const key of keys) {
        try {
            const r = await post(cfg.finishUrl.replace("{id}", key.slice(PENDING.length)), JSON.parse(store.getItem(key)))
            if (r.ok || (r.status >= 400 && r.status < 500)) store.removeItem(key)
        } catch (e) { /* still offline: keep it for next time */ }
    }
}

async function finish(attemptId, body) {
    // Up to 3 retries (1 s, 3 s, 9 s); then keep the result and send it on the next visit.
    const url = cfg.finishUrl.replace("{id}", attemptId)
    for (const wait of [0, 1000, 3000, 9000]) {
        if (wait) await sleep(wait)
        try {
            const r = await post(url, body)
            if (r.ok) return r.data
            // A 4xx is final (expired, signed out, invalid): say why; nothing is kept to resend.
            if (r.status >= 400 && r.status < 500) return {rejected: r.data?.error?.message || t.notSaved}
        } catch (e) { /* network error: retry */ }
    }
    try { storage()?.setItem(PENDING + attemptId, JSON.stringify(body)) } catch (e) { /* private mode */ }
    return null
}

function record(results, step, out) {
    const previous = results.get(step.id)
    if (!previous) {
        results.set(step.id, {id: step.id, tries: out.tries, hints: out.hints, ms: out.ms})
        return
    }
    previous.ms += out.ms
    if (step.type === "play_line") {
        previous.tries = previous.tries.map((list, k) => list.concat(out.tries[k] || []))
        previous.hints = previous.hints.map((n, k) => n + (out.hints[k] || 0))
    } else {
        previous.tries = previous.tries.concat(out.tries)
        previous.hints += out.hints
    }
}

async function main() {
    const ui = createUi(document.getElementById("player"), t)
    resendPending()
    let lesson
    try {
        const r = await fetch(cfg.lessonUrl, {credentials: "same-origin"})
        if (!r.ok) throw new Error(String(r.status))
        lesson = await r.json()
    } catch (e) {
        ui.error(t.loadError)
        return
    }
    ui.tag(lesson.lesson.title)

    let attemptId = null
    if (!cfg.preview) {
        let timezone = "UTC"
        try { timezone = Intl.DateTimeFormat().resolvedOptions().timeZone } catch (e) { /* keep UTC */ }
        const r = await post(cfg.attemptsUrl, {timezone}).catch(() => null)
        if (!r || !r.ok) {
            ui.error(t.loadError)
            return
        }
        attemptId = r.data.attempt_id
    }

    const board = createBoard(document.getElementById("board"),
                              {orientation: lesson.lesson.orientation, assetsUrl: cfg.assets, lang: cfg.lang})
    let combo = 0
    const ctx = {board, ui, t, lang: cfg.lang, orientation: lesson.lesson.orientation,
                 streak(ok) { combo = ok ? combo + 1 : 0; ui.combo(combo) }}
    const queue = new StepQueue(lesson.steps.filter(s => RUNNERS[s.type]))
    const results = new Map()
    const firstRun = new Set()
    let items = 0
    let correct = 0
    for (let step = queue.next(); step; step = queue.next()) {
        ui.progress(queue.done, queue.total)
        ui.reset()
        const out = await RUNNERS[step.type](step, ctx)
        record(results, step, out)
        if (!firstRun.has(step.id)) {
            firstRun.add(step.id)
            items += out.items
            correct += out.correct
        }
        queue.finish(step, out.requeue)
    }
    ui.progress(1, 1)
    const ms = [...results.values()].reduce((sum, r) => sum + r.ms, 0)
    if (cfg.preview) {
        ui.summary({preview: true, accuracy: items ? correct / items : 1, ms}, cfg)
        return
    }
    ui.saving()
    const result = await finish(attemptId, {steps: [...results.values()]})
    ui.summary(result ? {...result, ms} : {offline: true, ms}, cfg)  // null: kept to resend on the next visit
}

main()
