// Moves are computed in English SAN; French players read French piece letters.
const FRENCH = {K: "R", Q: "D", R: "T", B: "F", N: "C"}

export function localSan(san, lang) {
    if (lang !== "fr" || !san || san.startsWith("O-O")) return san
    const head = FRENCH[san[0]] ? FRENCH[san[0]] + san.slice(1) : san
    return head.replace(/=([QRBN])/, (_, piece) => "=" + FRENCH[piece])
}
