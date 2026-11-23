"""Glicko-2, as in Mark Glickman's "Example of the Glicko-2 system" (steps 2 to 8). Pure: no database.

Ratings are on the Glicko scale (1500 / 350); the algorithm works on the Glicko-2 scale (μ, φ).
"""
import math
from dataclasses import dataclass

SCALE = 173.7178
CENTRE = 1500.0
EPSILON = 0.000001


@dataclass(frozen=True)
class Rating:
    rating: float
    rd: float
    volatility: float


@dataclass(frozen=True)
class Game:
    rating: float  # the opponent's
    rd: float
    score: float  # 1 win, 0 loss


def _g(phi: float) -> float:
    return 1 / math.sqrt(1 + 3 * phi * phi / (math.pi * math.pi))


def _e(mu: float, mu_j: float, phi_j: float) -> float:
    return 1 / (1 + math.exp(-_g(phi_j) * (mu - mu_j)))


def expected(rating: float, opp_rating: float, opp_rd: float) -> float:
    """The expected score of `rating` against an opponent (Glicko-2's E)."""
    return _e((rating - CENTRE) / SCALE, (opp_rating - CENTRE) / SCALE, opp_rd / SCALE)


def _volatility(delta: float, phi: float, v: float, sigma: float, tau: float) -> float:
    """Step 5: the new volatility, by the Illinois algorithm."""
    a = math.log(sigma * sigma)

    def f(x: float) -> float:
        ex = math.exp(x)
        return (ex * (delta * delta - phi * phi - v - ex)) / (2 * (phi * phi + v + ex) ** 2) - (x - a) / (tau * tau)

    big_a = a
    if delta * delta > phi * phi + v:
        big_b = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        big_b = a - k * tau
    f_a, f_b = f(big_a), f(big_b)
    while abs(big_b - big_a) > EPSILON:
        c = big_a + (big_a - big_b) * f_a / (f_b - f_a)
        f_c = f(c)
        if f_c * f_b <= 0:
            big_a, f_a = big_b, f_b
        else:
            f_a /= 2
        big_b, f_b = c, f_c
    return math.exp(big_a / 2)


def rate(player: Rating, games: list[Game], tau: float) -> Rating:
    """The player's rating after one rating period with these games. No games: only the deviation grows."""
    mu, phi, sigma = (player.rating - CENTRE) / SCALE, player.rd / SCALE, player.volatility
    if not games:
        return Rating(player.rating, math.sqrt(phi * phi + sigma * sigma) * SCALE, sigma)
    opponents = [((g.rating - CENTRE) / SCALE, g.rd / SCALE, g.score) for g in games]
    v = 1 / sum(_g(phi_j) ** 2 * _e(mu, mu_j, phi_j) * (1 - _e(mu, mu_j, phi_j)) for mu_j, phi_j, _ in opponents)
    improvement = sum(_g(phi_j) * (s - _e(mu, mu_j, phi_j)) for mu_j, phi_j, s in opponents)
    delta = v * improvement
    new_sigma = _volatility(delta, phi, v, sigma, tau)
    phi_star = math.sqrt(phi * phi + new_sigma * new_sigma)
    new_phi = 1 / math.sqrt(1 / (phi_star * phi_star) + 1 / v)
    new_mu = mu + new_phi * new_phi * improvement
    return Rating(new_mu * SCALE + CENTRE, new_phi * SCALE, new_sigma)


def idle(player: Rating, periods: int, rd_max: float) -> Rating:
    """The rating after `periods` rating periods without games: φ* = √(φ² + periods·σ²), capped at rd_max."""
    if periods <= 0:
        return player
    phi = player.rd / SCALE
    rd = math.sqrt(phi * phi + periods * player.volatility ** 2) * SCALE
    return Rating(player.rating, min(rd, rd_max), player.volatility)
