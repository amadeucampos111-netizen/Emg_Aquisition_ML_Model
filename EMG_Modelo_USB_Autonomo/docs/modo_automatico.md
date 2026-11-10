# Fluxo de aquisição USB e classificação autónoma

1. Carregar `firmware/emg_stream_hc05/emg_stream_hc05.ino` no Uno.
2. Ligar o Arduino por USB e executar `python python/emg_assistant.py`.
3. Executar os gestos indicados no terminal; os dados são guardados em `data/emg_dataset.csv`.
4. O assistente chama `python/train_export.py`, que avalia o classificador e gera `firmware/emg_recognition_uno/model.h`.
5. Carregar `firmware/emg_recognition_uno/emg_recognition_uno.ino` no Uno.
6. Desligar o USB e alimentar o Uno de forma autónoma. O reconhecimento é executado localmente.

O PC é necessário para recolha, treino e atualização do modelo, mas não para a classificação final. A porta USB no modo final serve apenas para diagnóstico; o HC-05 é opcional e transmite apenas o resultado.


## Classes configuradas

O conjunto inicial tem cinco gestos: `mao_aberta`, `mao_fechada`, `repouso`, `flexao_polegar` e `thumbs_up`. A lista e as instruções de execução estão em `python/gesture_config.py`. Para adicionar classes, acrescenta uma entrada nesse dicionário, recolhe dados para todas as classes ativas e volta a treinar; o cabeçalho `model.h` é gerado com o novo número de classes.
