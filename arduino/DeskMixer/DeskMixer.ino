// --- CONSTANTS ---
const int NUM_SLIDERS = 4;
const int analogInputs[NUM_SLIDERS] = {33, 32, 35, 34};

const int NUM_BUTTONS = 6;
const int buttonInputs[NUM_BUTTONS] = {27, 25, 14, 26, 12, 13};

// Define the interval (in milliseconds) for sending slider data
const long SEND_INTERVAL_MS = 10; 

// Handshake constants
const String HANDSHAKE_REQUEST = "DeskMixer controller request";
const String HANDSHAKE_RESPONSE = "DeskMixer Controller Ready";

// --- GLOBAL VARIABLES ---

// Stores the current analog values for the sliders (0-1023)
int analogSliderValues[NUM_SLIDERS];

// Stores the current state of the buttons (1 for pressed, 0 for released)
int buttonValues[NUM_BUTTONS];

// Stores the state of the buttons from the previous loop iteration (for press detection)
int previousButtonValues[NUM_BUTTONS] = {0};

// Variable to store the last time slider data was sent
unsigned long lastSendTime = 0;

// Buffer for incoming serial data
String inputBuffer = "";


// --- SETUP ---

void setup() {
  // Initialize slider inputs
  for (int i = 0; i < NUM_SLIDERS; i++) {
    pinMode(analogInputs[i], INPUT);
  }

  // Initialize button inputs with internal pull-up resistors
  for (int i = 0; i < NUM_BUTTONS; i++) {
    pinMode(buttonInputs[i], INPUT_PULLUP);
  }

  // Set ADC resolution for consistent reading (0-1023 range for 10-bit)
  analogReadResolution(10);

  // Initialize serial communication
  Serial.begin(9600);

  // Wait for serial port to be ready
  delay(1000);

  // Send handshake response immediately on startup
  Serial.println(HANDSHAKE_RESPONSE);
}


// --- MAIN LOOP ---

void loop() {
  // 0. Check for incoming serial commands (handshake requests)
  checkSerialInput();

  // 1. Read all physical inputs
  // NOTE: This runs on every iteration of loop(), making buttons highly responsive.
  readCurrentValues();

  // 2. Check for and send one-shot button press events (separate lines, only sent on press)
  // NOTE: This runs on every iteration of loop() and bypasses the 10ms timing check.
  checkAndSendButtonEvents();

  // 3. Non-blocking check to send continuous slider data
  unsigned long currentMillis = millis();

  // Send the slider values only if the interval has passed
  if (currentMillis - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = currentMillis; // Save the last time the data was sent
    sendContinuousSliderValues();
  }

  // The loop is now non-blocking and will cycle as fast as possible,
  // making button detection immediate.
}


// --- SERIAL INPUT HANDLER ---

// Check for incoming serial commands (like handshake requests)
void checkSerialInput() {
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();

    if (inChar == '\n' || inChar == '\r') {
      // Process complete command
      if (inputBuffer.length() > 0) {
        processSerialCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      // Add character to buffer
      inputBuffer += inChar;
    }
  }
}


// Process received serial commands
void processSerialCommand(String command) {
  command.trim();

  // Handle handshake request
  if (command == HANDSHAKE_REQUEST) {
    Serial.println(HANDSHAKE_RESPONSE);
  }

  // Future commands can be added here (e.g., LED control, configuration, etc.)
}


// --- DATA READ FUNCTION ---

// Reads the current state of all analog sliders and digital buttons.
void readCurrentValues() {
  // Read analog sliders (continuous values)
  for (int i = 0; i < NUM_SLIDERS; i++) {
    analogSliderValues[i] = analogRead(analogInputs[i]);
  }

  // Read digital buttons (INPUT_PULLUP means LOW when pressed, so we invert it)
  for (int i = 0; i < NUM_BUTTONS; i++) {
    // 1 when pressed, 0 when released
    buttonValues[i] = !digitalRead(buttonInputs[i]);
  }
}


// --- DATA TRANSMISSION FUNCTIONS ---

// Sends all slider data on a single line continuously.
// Format: s1 512|s2 1023|...
void sendContinuousSliderValues() {
  // We use C-style strings and Serial.print for better performance on memory-constrained devices,
  // but keeping your original String object logic for consistency.
  String builtString = "";

  // Append Slider Values (s1, s2, s3, etc.)
  for (int i = 0; i < NUM_SLIDERS; i++) {
    builtString += "s";
    builtString += String(i + 1);
    builtString += " "; // Space is part of the required format
    builtString += String(analogSliderValues[i]);

    // Add separator only if it's not the last slider
    if (i < NUM_SLIDERS - 1) {
      builtString += "|";
    }
  }

  // Only print if there are sliders defined
  if (NUM_SLIDERS > 0) {
    Serial.println(builtString);
  }
}


// Checks for a press event (0 -> 1 transition) on any button and sends a separate line.
// This implements the one-shot press logic.
void checkAndSendButtonEvents() {
  for (int i = 0; i < NUM_BUTTONS; i++) {
    int current = buttonValues[i];
    int previous = previousButtonValues[i];

    // Check for a RISING EDGE (button just pressed: 0 -> 1)
    if (current == 1 && previous == 0) {
      // Button was just pressed. Send a separate line event: bX 1
      String eventString = "b";
      eventString += String(i + 1);
      eventString += " 1";
      Serial.println(eventString);

      // Note: We only send the '1' event (press). The system is silent on release.
    }

    // Update the previous state for the next loop iteration.
    // This allows us to detect the next press only after the button has been released (current=0)
    previousButtonValues[i] = current;
  }
}