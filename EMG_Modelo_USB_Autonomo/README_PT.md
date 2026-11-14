# Sistema sEMG autónomo — Arduino Uno R3 + 2 canais Grove EMG

## Objetivo e funcionamento

O projeto está dividido em duas fases. O computador só é necessário para recolher exemplos, treinar/avaliar o classificador e gerar os coeficientes C++ do modelo. Depois de carregar o firmware final, o Arduino faz a aquisição, extração de características e classificação localmente.

- **Treino por USB:** Arduino envia amostras EMG para o PC a 115200 baud; Python grava um CSV com etiquetas.
- **Treino no PC:** Python treina um classificador LinearSVC, avalia-o e exporta `model.h`.
- **Utilização autónoma:** `model.h` é compilado no Arduino. O Arduino reconhece os gestos sem PC. O USB pode ser desligado; a alimentação pode ser feita por uma fonte/bateria adequada.


> O `model.h` incluído inicialmente é apenas um placeholder. É obrigatório recolher dados e executar o treino antes de carregar o firmware de reconhecimento.

## 1. Ligações

### Dois sensores Grove EMG

| Sensor | Arduino Uno |
|---|---|
| EMG 1 — SIG | A0 |
| EMG 2 — SIG | A1 |
| VCC | Alimentação permitida pela revisão exata do sensor |
| GND | GND |

Confirma a tensão de alimentação e a amplitude máxima da saída analógica na documentação do teu módulo. Não assumes que todos os módulos Grove têm exatamente a mesma revisão.



## 2. Instalação do ambiente Python

Na pasta principal do projeto:

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Fase A — aquisição por USB

1. Abre `firmware/emg_stream_hc05/emg_stream_hc05.ino` na Arduino IDE.
2. Seleciona Arduino Uno e a porta COM correta.
3. Carrega o sketch.
4. Liga os sensores a A0 e A1 e abre o Monitor Série a **115200 baud**. Deverás ver linhas no formato `sequencia,adc1,adc2`. A linha de cabeçalho começa por `#` e é ignorada pelo programa Python.
5. Fecha o Monitor Série antes de iniciar o Python (uma porta COM não pode, normalmente, ser aberta por dois programas ao mesmo tempo).

O firmware recolhe 200 pares de amostras por segundo e envia os dois canais no mesmo pacote. O sketch de aquisição não necessita do HC-05.

Para testar o gráfico:

```bash
python python/plot_live.py --port COM7 --baud 115200
```

Substitui `COM7` pela porta apresentada no Gestor de Dispositivos do Windows.

## 4. Recolha de dados rotulados

Executa a recolha guiada:

```bash
python python/emg_assistant.py
```

O assistente procura automaticamente uma porta USB com pacotes EMG válidos, solicita cada gesto e guarda os dados em `data/emg_dataset.csv`. Também podes indicar a porta diretamente:

```bash
python python/emg_assistant.py --port COM7
```

Parâmetros úteis:

```bash
python python/emg_assistant.py --port COM7 --seconds 5 --repetitions 10
python python/emg_assistant.py --port COM7 --labels mao_aberta,mao_fechada,repouso,flexao_polegar,thumbs_up
```

A configuração inicial contém exatamente cinco gestos: `mao_aberta` (mão aberta), `mao_fechada` (punho fechado), `repouso` (mão relaxada), `flexao_polegar` (polegar fletido e restantes dedos estendidos/relaxados) e `thumbs_up` (quatro dedos fletidos e polegar estendido para cima). As etiquetas e descrições estão centralizadas em `python/gesture_config.py`.

### Como recolher corretamente

- Mantém os elétrodos na mesma posição durante uma sessão e identifica cada músculo/canal.
- Para cada gesto, faz várias repetições independentes, contraindo de forma semelhante e regressando ao repouso entre repetições.
- Evita movimento do braço/ombro que não faça parte do gesto.
- Faz pausas para evitar fadiga.
- Repete a recolha em mais do que uma sessão. Se possível, inclui uma sessão com os elétrodos novamente colocados para testar a robustez.
- Não recolhas apenas uma contração contínua longa: o modelo precisa de exemplos de execuções separadas.
- Mantém as etiquetas corretas. O programa assume que o gesto indicado no terminal é o que está a ser executado durante a gravação.

O assistente exige pelo menos duas classes e várias repetições independentes para treinar. Para uma avaliação mais representativa, aponta para 8–10 repetições por classe e várias sessões.

## 5. Fase B — treino, avaliação e exportação

No diretório principal:

```bash
python python/train_export.py
```

O programa:
1. Divide os dados por repetição, evitando que janelas sobrepostas da mesma repetição apareçam simultaneamente no treino e no teste.
2. Treina um classificador LinearSVC com normalização das características.
3. Apresenta acurácia, precisão/recall e matriz de confusão.
4. Treina novamente com todos os dados disponíveis.
5. Guarda `models/emg_linear_model.joblib` e gera `firmware/emg_recognition_uno/model.h`.

Também podes voltar a treinar sem recolher dados:

```bash
python python/emg_assistant.py --train-only
```

**Avalia a matriz de confusão, não apenas a acurácia.** Se dois gestos forem frequentemente confundidos, não assumas que o sistema consegue distingui-los de forma fiável. Recolhe mais dados, ajusta a posição dos sensores ou reduz o número de classes.

O valor `MODEL_MIN_GAP` é um limiar sobre a diferença entre pontuações do classificador, não é uma probabilidade. Se a diferença for pequena, o Arduino comunica `incerto`.


## 5A. Gestos iniciais e expansão futura

O sistema começa com estas cinco classes, definidas em `python/gesture_config.py`:

| Etiqueta | Gesto a executar |
|---|---|
| `mao_aberta` | Mão aberta, dedos estendidos |
| `mao_fechada` | Punho fechado |
| `repouso` | Mão relaxada, sem contração voluntária |
| `flexao_polegar` | Polegar fletido; restantes dedos estendidos e relaxados |
| `thumbs_up` | Quatro dedos fletidos e polegar estendido para cima |

**Para acrescentar um gesto mais tarde:**

1. Abre `python/gesture_config.py`.
2. Acrescenta uma entrada a `GESTURES`, usando uma etiqueta única com letras/números/underscore e no máximo 15 caracteres. Exemplo: `"pinça": ...` não é uma etiqueta válida para o firmware; usa `"pinca": "Polegar e indicador aproximados."`.
3. Executa novamente `python python/emg_assistant.py`. A nova classe passa a fazer parte da recolha guiada.
4. Recolhe exemplos de **todas** as classes ativas (as cinco iniciais e a nova), para que o dataset contenha dados comparáveis.
5. Executa o treino. O script filtra automaticamente etiquetas antigas que já não estejam em `GESTURES`, verifica se existem dados para todas as classes ativas e volta a gerar `model.h`.
6. Carrega novamente `emg_recognition_uno.ino` no Arduino.

Não é necessário alterar o código C++ do classificador para acrescentar classes: o número de classes e os coeficientes são gerados automaticamente em `model.h`. A única alteração manual habitual é em `gesture_config.py`.

## 6. Fase C — carregar o modelo no Arduino

Depois de o treino gerar `model.h`:

1. Abre `firmware/emg_recognition_uno/emg_recognition_uno.ino` na Arduino IDE.
2. Confirma que `model.h` está na mesma pasta do sketch.
3. Compila e carrega para o Arduino Uno.
4. Abre o Monitor Série a 115200 baud para diagnóstico. O resultado surge como `GESTO,nome_do_gesto,margem`.
5. Desliga o USB e alimenta o Arduino por uma fonte/bateria adequada. A classificação continua a funcionar localmente. O HC-05 pode enviar os mesmos resultados por Bluetooth, se estiver instalado.

O Arduino usa janelas de 100 amostras (0,5 s a 200 Hz) e atualiza a decisão a cada 50 amostras (0,25 s). A latência inclui a aquisição da primeira janela e o avanço da janela deslizante.

## 7. Integração com a mão biónica

O firmware atual **classifica e comunica o gesto; ainda não comanda servos**. Primeiro valida a classificação com a mão mecânica desligada. Depois associa cada etiqueta validada a uma posição/ação dos motores, implementando também:
- estado seguro por defeito quando a classificação é `incerto`;
- confirmação temporal/filtragem para evitar mudanças rápidas entre gestos;
- limites mecânicos e paragem de emergência;
- alimentação dos servos separada da alimentação lógica do Arduino, com GND comum;
- teste gradual sem colocar a mão de uma pessoa na zona de movimento.

Não alimentes os servos a partir do pino 5 V do Uno. A fonte dos motores deve suportar a corrente de arranque e de bloqueio dos servos.

## 8. Limitações importantes

- O modelo é específico dos sensores, da pessoa, da posição dos elétrodos e da montagem usada na recolha. Uma alteração importante pode exigir nova recolha e treino.
- Dois canais de EMG podem não conter informação suficiente para distinguir individualmente todos os dedos. A viabilidade deve ser demonstrada pela matriz de confusão e por testes com repetições/sessões independentes.
- A frequência de amostragem deste projeto está configurada para 200 Hz e as características são MAV, desvio-padrão/RMS centrado, comprimento da forma de onda, cruzamentos por zero e variância. Esta configuração é adequada apenas se o sinal disponibilizado pelo módulo tiver largura de banda compatível. Se estiveres a adquirir sEMG bruto, 200 Hz é geralmente insuficiente para representar a banda típica do EMG; será necessário confirmar o condicionamento do sensor e rever a taxa de amostragem e o processamento.
- O Arduino Uno tem apenas 2 KB de SRAM. Por isso foi escolhido um classificador linear compacto em vez de uma CNN pesada. O tamanho do `model.h` cresce com o número de classes.
- O limiar de margem não corresponde a uma confiança probabilística calibrada.
- Os módulos Grove EMG não são dispositivos médicos. Segue as instruções do fabricante e não ligues elétrodos a uma pessoa enquanto o circuito estiver ligado a equipamento alimentado pela rede sem isolamento adequado.

## 9. Estrutura dos ficheiros

- `firmware/emg_stream_hc05/`: firmware de aquisição por USB para criar o dataset.
- `firmware/emg_recognition_uno/`: firmware de classificação autónoma e `model.h`.
- `firmware/hc05_at_config/`: configuração opcional do HC-05.
- `python/collect_data.py`: recolha manual rotulada.
- `python/emg_assistant.py`: deteção da porta, recolha guiada e chamada do treino.
- `python/emg_common.py`: leitura dos pacotes e extração de características.
- `python/gesture_config.py`: lista central de gestos e descrições; editar este ficheiro para expandir o classificador.
- `python/train_export.py`: treino, avaliação e exportação dos coeficientes C++.
- `python/plot_live.py`: visualização dos sinais durante a aquisição.
- `data/`: dataset CSV.
- `models/`: modelo Python guardado para análise.
