"""Configuração central dos gestos reconhecidos pelo sistema EMG.

Para acrescentar um gesto: adiciona uma nova entrada ao dicionário GESTURES,
com uma etiqueta única (máx. 15 caracteres ASCII) e uma descrição clara.
Depois recolhe exemplos desse gesto e volta a executar train_export.py.
"""

GESTURES = {
    "mao_aberta": "Mão aberta: cinco dedos estendidos.",
    "mao_fechada": "Mão fechada: punho totalmente fechado.",
    "repouso": "Repouso: mão relaxada, sem contração voluntária.",
    "flexao_polegar": "Flexão do polegar: polegar fletido; restantes dedos estendidos e relaxados.",
    "thumbs_up": "Thumbs up: quatro dedos fletidos e polegar estendido para cima.",
}

# A ordem é usada no assistente de recolha. O modelo ordena as classes por si.
DEFAULT_LABELS = list(GESTURES.keys())
