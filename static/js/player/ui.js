// Everything on the lesson screen except the board. Text is always set with textContent.
export function createUi(root, t) {
    const $ = selector => root.querySelector(selector)
    const els = {
        tag: $(".lp-tag"), prompt: $(".lp-prompt"), coach: $(".lp-coach"), coachRow: $(".lp-coach-row"),
        chips: $(".lp-chips"), options: $(".lp-options"), hint: $(".lp-hint"), main: $(".lp-main"),
        feedback: $(".lp-feedback"), fbIcon: $(".lp-feedback__icon"), fbTitle: $(".lp-feedback__title"),
        fbText: $(".lp-feedback__text"), cont: $(".lp-continue"), progress: $(".lp-progress"),
        bar: $(".lp-progress > span"), combo: $(".lp-combo__n"), summary: $(".lp-summary"), error: $(".lp-error"),
    }
    let onHint = null
    els.hint.addEventListener("click", () => onHint && onHint())

    const el = (tag, className, text) => {
        const node = document.createElement(tag)
        if (className) node.className = className
        if (text !== undefined) node.textContent = text
        return node
    }

    const api = {
        tag(text) { els.tag.textContent = text || "" },
        prompt(text) { els.prompt.textContent = text || ""; els.prompt.hidden = !text },
        coach(text) { els.coach.textContent = text || ""; els.coachRow.hidden = !text },
        chips(list) {
            els.chips.replaceChildren(...list.map((san, i) => el("span", i === list.length - 1 ? "lp-chip is-new" : "lp-chip", san)))
        },
        hint(handler) { onHint = handler; els.hint.hidden = !handler },
        reset() {
            api.prompt(""); api.coach(""); api.chips([]); api.hint(null); els.options.replaceChildren()
        },
        progress(done, total) {
            const percent = total ? Math.round(100 * done / total) : 0
            els.bar.style.width = `${percent}%`
            els.progress.setAttribute("aria-valuenow", String(percent))
        },
        combo(n) { els.combo.textContent = String(n); els.combo.parentElement.classList.toggle("is-hot", n >= 3) },

        renderOptions(labels) {
            els.options.replaceChildren(...labels.map((label, i) => {
                const button = el("button", "lp-option", label)
                button.type = "button"
                button.dataset.option = String(i)
                return button
            }))
        },
        markOption(i, kind) {
            const button = els.options.querySelector(`[data-option="${i}"]`)
            if (button) button.classList.add(`is-${kind}`)
        },
        pickOption(only = null) {
            const buttons = [...els.options.querySelectorAll("[data-option]")]
            buttons.forEach(b => {
                const i = Number(b.dataset.option)
                b.disabled = b.classList.contains("is-bad") || (only !== null && i !== only)
            })
            return new Promise(resolve => {
                const pick = event => {
                    const button = event.target.closest("[data-option]")
                    if (!button || button.disabled) return
                    els.options.removeEventListener("click", pick)
                    buttons.forEach(b => { b.disabled = true })
                    resolve(Number(button.dataset.option))
                }
                els.options.addEventListener("click", pick)
            })
        },

        feedback({kind = "neutral", title = "", text = ""} = {}) {
            els.feedback.className = `lp-feedback is-${kind}`
            els.fbIcon.textContent = kind === "ok" ? "✓" : kind === "bad" ? "✕" : ""
            els.fbIcon.hidden = kind === "neutral"
            els.fbTitle.textContent = title
            els.fbText.textContent = text
            els.cont.textContent = t.continue
            els.cont.className = `cm-btn lp-continue ${kind === "bad" ? "cm-btn--danger" : "cm-btn--primary"}`
            els.feedback.hidden = false
            els.cont.focus({preventScroll: true})
            return new Promise(resolve => {
                const go = () => {
                    els.cont.removeEventListener("click", go)
                    els.feedback.hidden = true
                    resolve()
                }
                els.cont.addEventListener("click", go)
            })
        },

        error(message) {
            els.error.textContent = message
            els.error.hidden = false
        },
        saving() {
            els.main.hidden = true
            els.summary.replaceChildren(el("p", "lp-summary__saving", t.saving))
            els.summary.hidden = false
        },
        summary(result, cfg) {
            els.main.hidden = true
            els.feedback.hidden = true
            const box = els.summary
            box.replaceChildren()
            if (result.rejected) {
                box.append(el("div", "lp-summary__badge", "!"), el("h1", "lp-summary__title", t.notSaved),
                           el("p", "lp-summary__note", result.rejected))
                const actions = el("div", "lp-summary__actions")
                const again = el("a", "cm-btn cm-btn--primary", t.restart)
                again.href = location.pathname + location.search
                const back = el("a", "cm-btn cm-btn--secondary", t.backToPath)
                back.href = cfg.pathUrl
                actions.append(again, back)
                box.append(actions)
                box.hidden = false
                again.focus({preventScroll: true})
                return
            }
            const done = result.preview || result.offline || result.completed
            box.append(el("div", "lp-summary__badge", done ? "★" : "↻"))
            box.append(el("h1", "lp-summary__title", done ? t.lessonDone : t.lessonNotDone))
            if (result.preview) box.append(el("p", "lp-summary__note", t.preview))
            else if (result.offline) box.append(el("p", "lp-summary__note", t.savedLater))
            else if (result.xp) {
                box.append(el("div", "lp-summary__xp", `+${result.xp.awarded} XP`))
                if (result.xp.level_up) box.append(el("p", "lp-summary__level", t.levelUp))
            }
            const stats = el("div", "lp-summary__stats")
            const stat = (label, value) => {
                const card = el("div", "lp-summary__stat")
                card.append(el("div", "lp-summary__value", value), el("div", "cm-label", label))
                stats.append(card)
            }
            if (typeof result.accuracy === "number") stat(t.accuracy, `${Math.round(result.accuracy * 100)}%`)
            const seconds = Math.round((result.ms || 0) / 1000)
            stat(t.time, `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`)
            if (result.streak) stat(t.streak, String(result.streak.current))
            box.append(stats)
            for (const code of result.achievements || []) {
                box.append(el("div", "lp-summary__achievement", `🏅 ${t.achievements[code] || code}`))
            }
            const actions = el("div", "lp-summary__actions")
            const next = el("a", "cm-btn cm-btn--primary", t.backToPath)
            next.href = cfg.pathUrl
            actions.append(next)
            if (cfg.isGuest && !cfg.preview) {
                actions.append(el("p", "lp-summary__keep", t.keepProgress))
                const signup = el("a", "cm-btn cm-btn--secondary", t.createAccount)
                signup.href = cfg.signupUrl
                actions.append(signup)
            }
            box.append(actions)
            box.hidden = false
            next.focus({preventScroll: true})
        },
    }
    return api
}
