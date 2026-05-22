# Health Monitoring Arduino Code Reference

This file explains the purpose of the libraries, declarations, constants, and functions used in `health_monitoring.ino`.

## Libraries

- `#include <PulseSensorPlayground.h>` adds support for the pulse sensor. The code uses it to read heart beats and calculate BPM.
- `#include <OneWire.h>` adds OneWire communication support. The temperature sensor uses this communication line.
- `#include <DallasTemperature.h>` adds helper functions for Dallas temperature sensors. The code uses it to read body temperature in Celsius.
- `#include <LiquidCrystal_I2C.h>` adds support for an LCD screen that uses I2C. The code uses it to show BPM, risk status, and temperature.
- `#include <string.h>` adds string comparison functions. The code uses `strcmp()` to check commands received from Python.

## Constants and Declarations

- `#define ONE_WIRE_BUS 2` sets digital pin `2` as the data pin for the temperature sensor.
- `const unsigned long BEEP_HALF_MS = 200;` sets how long each buzzer on or off half-cycle lasts. This makes the buzzer toggle every 200 milliseconds when the patient is at risk.
- `OneWire oneWire(ONE_WIRE_BUS);` creates the OneWire connection on pin `2`.
- `DallasTemperature sensors(&oneWire);` creates the temperature sensor manager that uses the OneWire connection.
- `PulseSensorPlayground pulseSensor;` creates the pulse sensor object used to read BPM.
- `LiquidCrystal_I2C lcd(0x27, 16, 2);` creates a 16-column, 2-row LCD object at I2C address `0x27`.
- `const int PulseWire = A0;` sets analog pin `A0` as the pulse sensor input pin.
- `const int buzzer = 8;` sets digital pin `8` as the buzzer output pin.
- `static unsigned long lastBuzzerMs = 0;` stores the last time the buzzer changed state.
- `static bool buzzerOn = false;` stores whether the buzzer is currently on or off.
- `static bool pythonAtRisk = false;` stores the risk status sent by the Python program. `false` means normal, and `true` means at risk.

## Function: `updateBuzzerFromPython()`

This function controls the buzzer based on the latest risk status received from Python.

- `const unsigned long now = millis();` gets the current time since the Arduino started.
- `if (!pythonAtRisk)` checks if Python says the patient is not at risk.
- `digitalWrite(buzzer, LOW);` turns the buzzer off when the patient is normal.
- `buzzerOn = false;` records that the buzzer is off.
- `return;` stops the function early because no beeping is needed.
- `if (now - lastBuzzerMs >= BEEP_HALF_MS)` checks if 200 milliseconds have passed since the buzzer last changed.
- `lastBuzzerMs = now;` saves the current time as the latest buzzer change time.
- `buzzerOn = !buzzerOn;` flips the buzzer state from on to off, or from off to on.
- `digitalWrite(buzzer, buzzerOn ? HIGH : LOW);` turns the buzzer pin on when `buzzerOn` is true, or off when it is false.

## Function: `pollPythonCommand()`

This function reads text commands from Python through the serial port. It expects the commands `normal` or `at risk`.

- `static char cmdBuf[40];` creates a small text buffer to store the incoming command.
- `static uint8_t i = 0;` stores the current position inside the command buffer.
- `while (Serial.available() > 0)` keeps reading while there is serial data waiting.
- `char c = (char)Serial.read();` reads one character from the serial port.
- `if (c == '\r')` checks for a carriage return character.
- `continue;` skips carriage return characters.
- `if (c == '\n')` checks if the command line has ended.
- `cmdBuf[i] = '\0';` adds a string ending character so the buffer becomes normal C text.
- `i = 0;` resets the buffer position for the next command.
- `if (strcmp(cmdBuf, "normal") == 0)` checks if the received command is exactly `normal`.
- `pythonAtRisk = false;` stores normal status when Python sends `normal`.
- `else if (strcmp(cmdBuf, "at risk") == 0)` checks if the received command is exactly `at risk`.
- `pythonAtRisk = true;` stores at-risk status when Python sends `at risk`.
- `continue;` skips the rest of the loop because the command was already handled.
- `if (i < sizeof(cmdBuf) - 1)` checks if there is still space in the command buffer.
- `cmdBuf[i++] = (char)c;` stores the character and moves to the next buffer position.
- `else` runs when the command is too long for the buffer.
- `i = 0;` clears the buffer position so the next command can start fresh.

## Function: `setup()`

This function runs once when the Arduino starts. It prepares the serial port, sensors, LCD, pulse sensor, and buzzer.

- `Serial.begin(9600);` starts serial communication at 9600 baud so the Arduino can talk to Python.
- `sensors.begin();` starts the Dallas temperature sensor.
- `lcd.init();` starts the LCD screen.
- `lcd.backlight();` turns on the LCD backlight so the text is visible.
- `pulseSensor.analogInput(PulseWire);` tells the pulse sensor library to read from analog pin `A0`.
- `pulseSensor.setThreshold(550);` sets the signal level used to detect a heartbeat.
- `pulseSensor.begin();` starts the pulse sensor.
- `pinMode(buzzer, OUTPUT);` sets the buzzer pin as an output pin.
- `digitalWrite(buzzer, LOW);` makes sure the buzzer is off at startup.

## Function: `loop()`

This function runs again and again while the Arduino is powered on. It reads commands, gets sensor data, sends data to Python, updates the LCD, and controls the buzzer.

- `pollPythonCommand();` checks if Python sent a new risk status.
- `sensors.requestTemperatures();` asks the temperature sensor to take a new reading.
- `float temp = sensors.getTempCByIndex(0);` reads the first temperature sensor in Celsius.
- `int bpm = pulseSensor.getBeatsPerMinute();` reads the current heart rate in beats per minute.
- `updateBuzzerFromPython();` updates the buzzer using the latest Python risk status.
- `if (pulseSensor.sawStartOfBeat())` checks if a new heartbeat was detected.
- `Serial.print(bpm);` sends the BPM value to Python.
- `Serial.print(",");` sends a comma so Python can separate BPM and temperature.
- `Serial.println(temp, 1);` sends the temperature with one decimal place and ends the serial line.
- `static unsigned long lastLcdMs = 0;` stores the last time the LCD was refreshed.
- `const unsigned long now = millis();` gets the current Arduino time.
- `if (now - lastLcdMs >= 250)` checks if 250 milliseconds have passed since the last LCD refresh.
- `lastLcdMs = now;` saves the current time as the latest LCD refresh time.
- `lcd.setCursor(0, 0);` moves the LCD cursor to the first column of the first row.
- `lcd.print("HR:");` prints the heart rate label.
- `lcd.print(bpm);` prints the current BPM value.
- `lcd.print("    ");` prints spaces to clear old extra digits from the screen.
- `lcd.setCursor(14, 0);` moves the cursor near the end of the first row.
- `lcd.print(pythonAtRisk ? "R" : "N");` prints `R` for at risk or `N` for normal.
- `lcd.setCursor(0, 1);` moves the LCD cursor to the first column of the second row.
- `if (temp == DEVICE_DISCONNECTED_C)` checks if the temperature sensor is disconnected or not giving a valid reading.
- `lcd.print("Temp: --.-C     ");` shows a placeholder when temperature is not available.
- `else` runs when the temperature reading is valid.
- `lcd.print("Temp:");` prints the temperature label.
- `lcd.print(temp, 1);` prints the temperature with one decimal place.
- `lcd.print("C     ");` prints the Celsius unit and spaces to clear old characters.
- `delay(20);` waits 20 milliseconds before the next loop cycle. This keeps the loop from running too fast.

## Data Flow Summary

The Arduino reads BPM from the pulse sensor and temperature from the Dallas temperature sensor. When a heartbeat is detected, it sends `BPM,temperature` to Python through serial communication. Python sends back either `normal` or `at risk`. The Arduino shows the values on the LCD and turns the buzzer on and off when the status is `at risk`.
