// Ficheiro placeholder. Será substituído por python/train_export.py.
#pragma once
#include <avr/pgmspace.h>
#define MODEL_VALID 0
#define MODEL_N_CLASSES 1
#define MODEL_N_FEATURES 10
#define MODEL_MIN_GAP 0.35f
const char MODEL_LABELS[MODEL_N_CLASSES][16] PROGMEM = {"SEM_MODELO"};
const float MODEL_MEAN[MODEL_N_FEATURES] PROGMEM = {0,0,0,0,0,0,0,0,0,0};
const float MODEL_SCALE[MODEL_N_FEATURES] PROGMEM = {1,1,1,1,1,1,1,1,1,1};
const float MODEL_COEF[MODEL_N_CLASSES][MODEL_N_FEATURES] PROGMEM = {{0,0,0,0,0,0,0,0,0,0}};
const float MODEL_BIAS[MODEL_N_CLASSES] PROGMEM = {0};
