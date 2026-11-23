// The board: cm-chessboard for drawing and input, chess.js for the rules. Only legal moves can be played.
import {Chessboard, COLOR, FEN, INPUT_EVENT_TYPE} from "../../vendor/cm-chessboard/src/Chessboard.js"
import {Arrows, ARROW_TYPE} from "../../vendor/cm-chessboard/src/extensions/arrows/Arrows.js"
import {Markers, MARKER_TYPE} from "../../vendor/cm-chessboard/src/extensions/markers/Markers.js"
import {PromotionDialog} from "../../vendor/cm-chessboard/src/extensions/promotion-dialog/PromotionDialog.js"
import {Accessibility} from "../../vendor/cm-chessboard/src/extensions/accessibility/Accessibility.js"
import {Chess} from "../../vendor/chess.js/chess.js"

export const turnOf = fen => (fen.split(" ")[1] === "b" ? "black" : "white")

export function after(fen, uci) {
    const game = new Chess(fen)
    const move = game.move(uci)
    return {fen: game.fen(), san: move.san}
}

export function createBoard(el, {orientation, assetsUrl, lang}) {
    const board = new Chessboard(el, {
        position: FEN.empty, assetsUrl,
        orientation: orientation === "black" ? COLOR.black : COLOR.white,
        style: {cssClass: "default", showCoordinates: true, animationDuration: 250},
        extensions: [
            {class: Markers},
            {class: Arrows},
            {class: PromotionDialog},
            {class: Accessibility, props: {language: lang, boardAsTable: false, piecesAsList: false,
                                           movePieceForm: true, visuallyHidden: true}},
        ],
    })

    function waitForMove(fen, forced = null) {
        // Resolves with the UCI of the learner's legal move. With `forced`, only that move can be played.
        return new Promise(resolve => {
            const game = new Chess(fen)
            const color = game.turn() === "w" ? COLOR.white : COLOR.black
            const legal = from => game.moves({square: from, verbose: true})
                .filter(m => !forced || (m.from === forced.slice(0, 2) && m.to === forced.slice(2, 4)))
            let pending = null
            const done = uci => {
                board.disableMoveInput()
                board.removeLegalMovesMarkers()
                el.dataset.input = "off"
                resolve(uci)
            }
            board.enableMoveInput(event => {
                switch (event.type) {
                    case INPUT_EVENT_TYPE.moveInputStarted: {
                        const moves = legal(event.squareFrom)
                        board.removeLegalMovesMarkers()
                        board.addLegalMovesMarkers(moves)
                        return moves.length > 0
                    }
                    case INPUT_EVENT_TYPE.validateMoveInput: {
                        board.removeLegalMovesMarkers()
                        const options = legal(event.squareFrom).filter(m => m.to === event.squareTo)
                        if (!options.length) return false
                        if (options.some(m => m.promotion)) {
                            board.showPromotionDialog(event.squareTo, color, result => {
                                if (result && result.piece) done(event.squareFrom + event.squareTo + result.piece.charAt(1))
                                else board.setPosition(fen, false)
                            })
                            return true
                        }
                        pending = event.squareFrom + event.squareTo
                        return true
                    }
                    case INPUT_EVENT_TYPE.moveInputFinished:
                        if (pending) {
                            const uci = pending
                            pending = null
                            done(uci)
                        }
                        return
                    case INPUT_EVENT_TYPE.moveInputCanceled:
                        board.removeLegalMovesMarkers()
                        return
                }
            }, color)
            el.dataset.input = "on"  // the board now takes a move (tests and assistive tech can wait for this)
        })
    }

    return {
        waitForMove,
        async setFen(fen, animate = true) {
            board.disableMoveInput()
            el.dataset.input = "off"
            await board.setPosition(fen, animate)
        },
        async orient(color) {
            const wanted = color === "black" ? COLOR.black : COLOR.white
            if (board.getOrientation() !== wanted) await board.setOrientation(wanted, false)
        },
        async play(fen, uci) {
            const next = after(fen, uci)
            await board.setPosition(next.fen, true)
            return next
        },
        arrows(list) {
            board.removeArrows()
            for (const [from, to, kind] of list) board.addArrow(ARROW_TYPE[kind] || ARROW_TYPE.info, from, to)
        },
        mark(squares, kind = "frame") {
            board.removeMarkers(MARKER_TYPE.framePrimary)
            board.removeMarkers(MARKER_TYPE.circlePrimary)
            const type = kind === "hint" ? MARKER_TYPE.circlePrimary : MARKER_TYPE.framePrimary
            for (const square of squares) board.addMarker(type, square)
        },
        clear() {
            board.removeArrows()
            board.removeMarkers(MARKER_TYPE.framePrimary)
            board.removeMarkers(MARKER_TYPE.circlePrimary)
        },
        shake() {
            el.classList.remove("lp-shake")
            void el.offsetWidth
            el.classList.add("lp-shake")
        },
    }
}
