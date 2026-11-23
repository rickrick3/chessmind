// The order steps are played in. A step answered wrong on the first try comes back once, at the end.
export class StepQueue {
    constructor(steps) {
        this.items = [...steps]
        this.requeued = new Set()
        this.done = 0
    }

    get total() {
        return this.done + this.items.length
    }

    next() {
        return this.items.shift() || null
    }

    finish(step, again) {
        this.done += 1
        if (again && !this.requeued.has(step.id)) {
            this.requeued.add(step.id)
            this.items.push(step)
        }
    }
}
