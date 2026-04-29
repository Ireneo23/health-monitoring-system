#include <PulseSensorPlayground.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <LiquidCrystal_I2C.h>

#include <ctype.h>
#include <string.h>
#include <stddef.h>

#define ONE_WIRE_BUS 2

// Thresholds aligned with python/health_data.csv (0=Normal, 1=At risk) — LCD only
const int BPM_AT_RISK_LOW = 59;
const int BPM_AT_RISK_HIGH = 101;
const float TEMP_AT_RISK_LOW = 35.9f;
const float TEMP_AT_RISK_HIGH = 37.5f;
const float TEMP_VALID_MIN = 20.0f;
const float TEMP_VALID_MAX = 45.0f;

const unsigned long BEEP_HALF_MS = 200;

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

PulseSensorPlayground pulseSensor;
LiquidCrystal_I2C lcd(0x27, 16, 2);

const int PulseWire = A0;
const int buzzer = 8;

static unsigned long lastBuzzerMs = 0;
static bool buzzerOn = false;

/** True after Python sends "at risk"; false otherwise (starts safe). */
static bool pythonAtRisk = false;

/** @return 1 = High (LCD), 0 = Low — sensor rules only */
int computeLabel(int bpm, float temp) {
  const bool tOk = (temp > TEMP_VALID_MIN) && (temp < TEMP_VALID_MAX);
  if (!tOk) return 0;
  if (bpm <= BPM_AT_RISK_LOW) return 1;
  if (bpm >= BPM_AT_RISK_HIGH) return 1;
  if (temp <= TEMP_AT_RISK_LOW) return 1;
  if (temp >= TEMP_AT_RISK_HIGH) return 1;
  return 0;
}

static void trimInPlace(char* s) {
  if (!s) return;
  size_t len = strlen(s);
  size_t start = 0;
  while (s[start] == ' ' || s[start] == '\t') start++;
  if (start > 0 && start <= len) {
    memmove(s, s + start, len - start + 1);
  }
  len = strlen(s);
  while (len > 0 && (s[len - 1] == ' ' || s[len - 1] == '\t' || s[len - 1] == '\r')) {
    s[--len] = '\0';
  }
}

static void lowerInPlace(char* dest, const char* src, size_t cap) {
  size_t i = 0;
  for (; src[i] && i + 1 < cap; i++) {
    dest[i] = (char)tolower((unsigned char)src[i]);
  }
  dest[i] = '\0';
}

void updateBuzzerFromPython() {
  const unsigned long now = millis();
  if (!pythonAtRisk) {
    digitalWrite(buzzer, LOW);
    buzzerOn = false;
    lastBuzzerMs = now;
    return;
  }
  if (now - lastBuzzerMs >= BEEP_HALF_MS) {
    lastBuzzerMs = now;
    buzzerOn = !buzzerOn;
    digitalWrite(buzzer, buzzerOn ? HIGH : LOW);
  }
}

void pollPythonCommand() {
  static char cmdBuf[40];
  static uint8_t i = 0;

  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      cmdBuf[i] = '\0';
      i = 0;
      trimInPlace(cmdBuf);
      char low[sizeof(cmdBuf)];
      lowerInPlace(low, cmdBuf, sizeof(low));
      if (strcmp(low, "normal") == 0) {
        pythonAtRisk = false;
      } else if (strcmp(low, "at risk") == 0) {
        pythonAtRisk = true;
      }
      continue;
    }
    if (i < sizeof(cmdBuf) - 1) {
      cmdBuf[i++] = (char)c;
    } else {
      i = 0;
    }
  }
}

void setup() {
  Serial.begin(9600);

  sensors.begin();

  lcd.init();
  lcd.backlight();

  pulseSensor.analogInput(PulseWire);
  pulseSensor.setThreshold(550);
  pulseSensor.begin();

  pinMode(buzzer, OUTPUT);
  digitalWrite(buzzer, LOW);
}

void loop() {
  pollPythonCommand();

  sensors.requestTemperatures();
  float temp = sensors.getTempCByIndex(0);

  int bpm = pulseSensor.getBeatsPerMinute();
  int label = computeLabel(bpm, temp);
  updateBuzzerFromPython();

  if (pulseSensor.sawStartOfBeat()) {
    Serial.print(bpm);
    Serial.print(",");
    Serial.println(temp, 1);

    // H/L = sensor rule thresholds (LCD only); buzzer = Python status
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("HR:");
    lcd.print(bpm);
    lcd.setCursor(14, 0);
    lcd.print(label == 1 ? "H" : "L");

    lcd.setCursor(0, 1);
    lcd.print("Temp:");
    lcd.print(temp, 1);
  }

  delay(20);
}
