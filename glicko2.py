# glicko2.py
import math

TAU = 0.5
MU = 1500
PHI = 350
SIGMA = 0.06

def g(phi):
    return 1 / math.sqrt(1 + 3 * phi**2 / math.pi**2)

def E(mu, mu_j, phi_j):
    return 1 / (1 + math.exp(-g(phi_j) * (mu - mu_j)))

def update_rating(mu, phi, sigma, results):
    v_inv = sum((g(pj)**2) * E(mu, muj, pj) * (1 - E(mu, muj, pj)) for muj, pj, _ in results)
    v = 1 / v_inv

    delta = v * sum(g(pj) * (s - E(mu, muj, pj)) for muj, pj, s in results)

    phi_star = math.sqrt(phi**2 + sigma**2)
    phi_new = 1 / math.sqrt((1 / phi_star**2) + (1 / v))
    mu_new = mu + phi_new**2 * sum(g(pj) * (s - E(mu, muj, pj)) for muj, pj, s in results)

    return mu_new, phi_new, sigma
