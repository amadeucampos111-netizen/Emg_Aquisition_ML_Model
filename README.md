# Autonomous sEMG System — Arduino Uno R3 + 2 Grove EMG Channels

## Objective and Operation

The project is divided into two phases. The computer is only required to collect examples, train/evaluate the classifier, and generate the C++ model coefficients. After uploading the final firmware, the Arduino performs data acquisition, feature extraction, and classification locally.

- **Training via USB:** Arduino sends EMG samples to the PC at 115200 baud; Python records a labeled CSV.
- **Training on PC:** Python trains a LinearSVC classifier, evaluates it, and exports `model.h`.
- **Autonomous operation:** `model.h` is compiled onto the Arduino. The Arduino recognizes gestures without a PC. The USB can be disconnected; power can be supplied by a suitable power supply/battery.

> The initially included `model.h` is just a placeholder. It is mandatory to collect data and run the training before uploading the recognition firmware.

## 1. Wiring / Connections

### Two Grove EMG Sensors

| Sensor | Arduino Uno |
|---|---|
| EMG 1 — SIG | A0 |
| EMG 2 — SIG | A1 |
| VCC | Power supply permitted by the exact sensor revision |
| GND | GND |

Confirm the supply voltage and maximum analog output amplitude in your module's documentation. Do not assume all Grove modules have the exact same revision.

## 2. Python Environment Setup

In the project's root folder:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Phase A — Acquisition via USB

1. Open `firmware/emg_stream_hc05/emg_stream_hc05.ino` in the Arduino IDE.
2. Select Arduino Uno and the correct COM port.
3. Upload the sketch.
4. Connect the sensors to A0 and A1 and open the Serial Monitor at **115200 baud**. You should see lines in the format `sequence,adc1,adc2`. The header line starts with `#` and is ignored by the Python program.
5. Close the Serial Monitor before starting Python (a COM port cannot normally be opened by two programs at the same time).

The firmware collects 200 pairs of samples per second and sends both channels in the same packet. The acquisition sketch does not require the HC-05 module.

To test the live plot:

```bash
python python/plot_live.py --port COM7 --baud 115200
```

Replace `COM7` with the port shown in Windows Device Manager.

## 4. Labeled Data Collection

Run the guided collection:

```bash
python python/emg_assistant.py
```

The assistant automatically searches for a USB port with valid EMG packets, prompts for each gesture, and saves the data to `data/emg_dataset.csv`. You can also specify the port directly:

```bash
python python/emg_assistant.py --port COM7
```

Useful parameters:

```bash
python python/emg_assistant.py --port COM7 --seconds 5 --repetitions 10
python python/emg_assistant.py --port COM7 --labels mao_aberta,mao_fechada,repouso,flexao_polegar,thumbs_up
```

The initial configuration contains exactly five gestures: `mao_aberta` (open hand), `mao_fechada` (closed fist), `repouso` (relaxed hand), `flexao_polegar` (thumb flexed and remaining fingers extended/relaxed), and `thumbs_up` (four fingers flexed and thumb extended upward). Labels and descriptions are centralized in `python/gesture_config.py`.

### How to Collect Properly

- Keep the electrodes in the same position during a session and identify each muscle/channel.
- For each gesture, perform several independent repetitions, contracting similarly and returning to rest between repetitions.
- Avoid arm/shoulder movements that are not part of the gesture.
- Take breaks to avoid fatigue.
- Repeat the collection across more than one session. If possible, include a session where the electrodes are reapplied to test robustness.
- Do not collect just one long continuous contraction: the model needs examples of separate executions.
- Keep the labels accurate. The program assumes that the gesture shown in the terminal is the one being performed during recording.

The assistant requires at least two classes and several independent repetitions to train. For a more representative evaluation, aim for 8–10 repetitions per class across multiple sessions.

## 5. Phase B — Training, Evaluation, and Export

In the root directory:

```bash
python python/train_export.py
```

The program:
1. Splits the data by repetition, preventing overlapping windows from the same repetition from appearing simultaneously in both training and test sets.
2. Trains a LinearSVC classifier with feature standardization.
3. Displays accuracy, precision/recall, and the confusion matrix.
4. Retrains using all available data.
5. Saves `models/emg_linear_model.joblib` and generates `firmware/emg_recognition_uno/model.h`.

You can also retrain without collecting new data:

```bash
python python/emg_assistant.py --train-only
```

**Evaluate the confusion matrix, not just accuracy.** If two gestures are frequently confused, do not assume the system can reliably distinguish them. Collect more data, adjust sensor placement, or reduce the number of classes.

The `MODEL_MIN_GAP` value is a threshold on the difference between classifier scores, not a probability. If the difference is small, the Arduino outputs `incerto` (uncertain).

## 5A. Initial Gestures and Future Expansion

The system starts with these five classes, defined in `python/gesture_config.py`:

| Label | Gesture to Perform |
|---|---|
| `mao_aberta` | Open hand, fingers extended |
| `mao_fechada` | Closed fist |
| `repouso` | Relaxed hand, no voluntary contraction |
| `flexao_polegar` | Thumb flexed; remaining fingers extended and relaxed |
| `thumbs_up` | Four fingers flexed and thumb extended upward |

**To add a gesture later:**

1. Open `python/gesture_config.py`.
2. Add an entry to `GESTURES`, using a unique label with letters/numbers/underscores and a maximum of 15 characters. Example: `"pinça": ...` is not a valid label for the firmware; use `"pinca": "Thumb and index finger brought together."`.
3. Run `python python/emg_assistant.py` again. The new class becomes part of the guided collection.
4. Collect examples of **all** active classes (the five initial ones and the new one) so that the dataset contains comparable data.
5. Run the training. The script automatically filters out old labels that are no longer in `GESTURES`, verifies that data exists for all active classes, and regenerates `model.h`.
6. Re-upload `emg_recognition_uno.ino` to the Arduino.

You do not need to modify the C++ classifier code to add classes: the number of classes and coefficients are automatically generated in `model.h`. The only usual manual change is in `gesture_config.py`.

## 6. Phase C — Uploading the Model to the Arduino

After training generates `model.h`:

1. Open `firmware/emg_recognition_uno/emg_recognition_uno.ino` in the Arduino IDE.
2. Confirm that `model.h` is in the same folder as the sketch.
3. Compile and upload to the Arduino Uno.
4. Open the Serial Monitor at 115200 baud for diagnostics. The output appears as `GESTO,gesture_name,margin`.
5. Disconnect the USB and power the Arduino via a suitable power supply/battery. Classification continues to run locally. The HC-05 can send the same results via Bluetooth, if installed.

The Arduino uses windows of 100 samples (0.5 s at 200 Hz) and updates the decision every 50 samples (0.25 s). Latency includes acquiring the first window and advancing the sliding window.

## 7. Integration with the Bionic Hand

The current firmware **classifies and outputs the gesture; it does not yet drive servos**. First, validate the classification with the mechanical hand disconnected. Then map each validated label to a motor position/action, while also implementing:
- a safe default state when the classification is `incerto` (uncertain);
- temporal confirmation/filtering to prevent rapid switching between gestures;
- mechanical limits and an emergency stop;
- separate servo power supply from the Arduino logic power supply, sharing a common GND;
- gradual testing without placing a person's hand in the movement zone.

Do not power servos from the Uno's 5 V pin. The motor power supply must handle the startup and stall current of the servos.

## 8. Important Limitations

- The model is specific to the sensors, person, electrode placement, and setup used during collection. Any major change may require new data collection and training.
- Two EMG channels may not contain enough information to distinguish every finger individually. Feasibility must be demonstrated by the confusion matrix and tests with independent repetitions/sessions.
- The sampling rate of this project is configured to 200 Hz, and the features are MAV, standard deviation/centered RMS, waveform length, zero crossings, and variance. This configuration is only suitable if the signal provided by the module has a compatible bandwidth. If you are acquiring raw sEMG, 200 Hz is generally insufficient to represent the typical EMG bandwidth; you will need to confirm sensor conditioning and review the sampling rate and processing.
- The Arduino Uno has only 2 KB of SRAM. Therefore, a compact linear classifier was chosen instead of a heavy CNN. The size of `model.h` grows with the number of classes.
- The margin threshold does not correspond to a calibrated probabilistic confidence.
- Grove EMG modules are not medical devices. Follow the manufacturer's instructions and do not attach electrodes to a person while the circuit is connected to mains-powered equipment without proper isolation.

## 9. File Structure

- `firmware/emg_stream_hc05/`: USB acquisition firmware to create the dataset.
- `firmware/emg_recognition_uno/`: autonomous classification firmware and `model.h`.
- `firmware/hc05_at_config/`: optional HC-05 configuration.
- `python/collect_data.py`: manual labeled collection.
- `python/emg_assistant.py`: port detection, guided collection, and training trigger.
- `python/emg_common.py`: packet reading and feature extraction.
- `python/gesture_config.py`: central list of gestures and descriptions; edit this file to expand the classifier.
- `python/train_export.py`: training, evaluation, and export of C++ coefficients.
- `python/plot_live.py`: signal visualization during acquisition.
- `data/`: CSV dataset.
- `models/`: saved Python model for analysis.