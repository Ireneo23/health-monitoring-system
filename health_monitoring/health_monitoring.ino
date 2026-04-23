#include <OneWire.h>
#include <DallasTemperature.h>
#include <LiquidCrystal_I2C.h>
#include <SoftwareSerial.h>

#define ONE_WIRE_BUS 2
#define PULSE_PIN A0
#define BUZZER 8

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

LiquidCrystal_I2C lcd(0x27, 16, 2);

SoftwareSerial bluetooth(10, 11); // RX, TX

void setup() {
  Serial.begin(9600);
  bluetooth.begin(9600);

  sensors.begin();
  lcd.init();
  lcd.backlight();

  pinMode(BUZZER, OUTPUT);
}

void loop() {
  sensors.requestTemperatures();
  float temp = sensors.getTempCByIndex(0);

  int pulse = analogRead(PULSE_PIN);

  lcd.setCursor(0, 0);
  lcd.print("Temp:");
  lcd.print(temp);

  lcd.setCursor(0, 1);
  lcd.print("Pulse:");
  lcd.print(pulse);

  // Alert
  if (pulse > 700) {
    digitalWrite(BUZZER, HIGH);
  } else {
    digitalWrite(BUZZER, LOW);
  }

  // Send data to Python
  Serial.print(temp);
  Serial.print(",");
  Serial.println(pulse);

  bluetooth.print(temp);
  bluetooth.print(",");
  bluetooth.println(pulse);

  delay(1000);
}