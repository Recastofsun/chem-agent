import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
from chem_agent.uncertainty.ensemble import draws
from chem_agent.uncertainty.propagation import sigma_sum, sigma_sum_corr

if __name__ == "__main__":
    N = 4
    sigmas = np.array([1.0, 1.0, 1.0, 1.0])
    # Реакция Zn + CuSO4 -> Cu + ZnSO4
    sources = ["CRC", "CRC", "CRC", "CRC"]
    idx_coefs = [(0, -1.0), (1, -1.0), (2, 1.0), (3, 1.0)]

    # 1. Старый способ (независимые ошибки)
    old_std = sigma_sum([(c, sigmas[i]) for i, c in idx_coefs])
    print(f"Ошибка энергии без ковариации: {old_std:.3f} кДж/моль")

    # 2. Новый способ (с ковариацией)
    new_std = sigma_sum_corr(idx_coefs, sigmas, sources, rho=0.9)
    print(f"Ошибка энергии с ковариацией: {new_std:.3f} кДж/моль")

    # 3. Проверка через Монте-Карло
    D = draws(sigmas, 100000, 42, sources=sources, rho=0.9)
    sum_D = D[:, 0] * -1.0 + D[:, 1] * -1.0 + D[:, 2] * 1.0 + D[:, 3] * 1.0
    print(f"Эмпирическая ошибка Монте-Карло: {sum_D.std():.3f} кДж/моль")