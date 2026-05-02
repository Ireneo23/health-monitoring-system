#include <PulseSensorPlayground.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <LiquidCrystal_I2C.h>

#include <string.h>

#define ONE_WIRE_BUS 2

const unsigned long BEEP_HALF_MS = 200;

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

PulseSensorPlayground pulseSensor;
LiquidCrystal_I2C lcd(0x27, 16, 2);

const int PulseWire = A0;
const int buzzer = 8;

static unsigned long lastBuzzerMs = 0;
static bool buzzerOn = false;

/** Matches Python serial commands: "normal" / "at risk" (exact, lowercase). */
static bool pythonAtRisk = false;

void updateBuzzerFromPython()
{
  const unsigned long now = millis();
  if (!pythonAtRisk)
  {
    digitalWrite(buzzer, LOW);
    buzzerOn = false;
    return;
  }
  if (now - lastBuzzerMs >= BEEP_HALF_MS)
  {
    lastBuzzerMs = now;
    buzzerOn = !buzzerOn;
    digitalWrite(buzzer, buzzerOn ? HIGH : LOW);
  }
}

void pollPythonCommand()
{
  static char cmdBuf[40];
  static uint8_t i = 0;

  while (Serial.available() > 0)
  {
    char c = (char)Serial.read();
    if (c == '\r')
      continue;
    if (c == '\n')
    {
      cmdBuf[i] = '\0';
      i = 0;
      if (strcmp(cmdBuf, "normal") == 0)
      {
        pythonAtRisk = false;
      }
      else if (strcmp(cmdBuf, "at risk") == 0)
      {
        pythonAtRisk = true;
      }
      continue;
    }
    if (i < sizeof(cmdBuf) - 1)
    {
      cmdBuf[i++] = (char)c;
    }
    else
    {
      i = 0;
    }
  }
}

void setup()
{
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

void loop()
{
  pollPythonCommand();

  sensors.requestTemperatures();
  float temp = sensors.getTempCByIndex(0);

  int bpm = pulseSensor.getBeatsPerMinute();
  updateBuzzerFromPython();

  if (pulseSensor.sawStartOfBeat())
  {
    Serial.print(bpm);
    Serial.print(",");
    Serial.println(temp, 1);
  }

  // This selected block updates the LCD screen every 250 milliseconds.
  //  Its purpose is to show the latest heart rate, risk status, and temperature
  //  without refreshing the screen too fast.
  static unsigned long lastLcdMs = 0;
  const unsigned long now = millis();
  if (now - lastLcdMs >= 250)
  {
    lastLcdMs = now;
    // Row 0: HR + R/N from Python (buzzer follows same flag).
    lcd.setCursor(0, 0);
    lcd.print("HR:");
    lcd.print(bpm);
    lcd.print("    "); // overwrite leftovers when digits shrink
    lcd.setCursor(14, 0);
    lcd.print(pythonAtRisk ? "R" : "N");

    // Row 1: Temperature
    lcd.setCursor(0, 1);
    if (temp == DEVICE_DISCONNECTED_C)
    {
      lcd.print("Temp: --.-C     ");
    }
    else
    {
      lcd.print("Temp:");
      lcd.print(temp, 1);
      lcd.print("C     "); // pad to clear old chars
    }
  }

  delay(20);
}
