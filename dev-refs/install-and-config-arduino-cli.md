Installing and configuring `arduino-cli` (Arduino Command Line Interface) is a great way to move your Arduino development out of the standard IDE and into your terminal, favorite text editor, or CI/CD pipelines. 

Here is the straightforward guide to getting it up and running on your system.

### **Step 1: Installation**

Choose the method that matches your operating system:

**macOS**
The easiest way is using Homebrew:
```bash
brew install arduino-cli
```

**Windows**
You can use `winget` (Windows Package Manager) in your Command Prompt or PowerShell:
```powershell
# WRONG: winget install Arduino.arduino-cli
winget install ArduinoSA.CLI
```
*Alternatively, you can use Chocolatey (`choco install arduino-cli`) or download the pre-compiled `.zip` from the [Arduino GitHub Releases page](https://github.com/arduino/arduino-cli/releases) and add it to your system PATH.*

**Linux**
You can use the official installation script. Open your terminal and run:
```bash
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
```
This installs the binary into a `bin` folder in your current directory. To make it globally accessible, move it to your user binaries:
```bash
sudo mv bin/arduino-cli /usr/local/bin/
```

Verify the installation was successful by checking the version:
```bash
arduino-cli version
```

---

### **Step 2: Initial Configuration**

Once installed, you need to set up the configuration file and download the index of available boards and libraries.

**1. Generate the configuration file**
This creates an `arduino-cli.yaml` file that stores your preferences (URLs, directories, etc.).
```bash
arduino-cli config init
```
*(By default, this saves to `~/.arduino15/` on Mac/Linux or `%LOCALAPPDATA%\Arduino15\` on Windows).*

**2. Update the core index**
Before you can install any boards, you need to pull the latest list of available platforms (similar to `apt update` or `brew update`).
```bash
arduino-cli core update-index
```

---

### **Step 3: Installing a Board Core**

`arduino-cli` doesn't come with board definitions pre-installed. You need to install the specific "core" for the microcontroller you are using. 

**1. Find your board**
Plug your Arduino into your computer via USB and run:
```bash
arduino-cli board list
```
You will see an output listing the Port, Type, Board Name, and the **FQBN** (Fully Qualified Board Name). For a standard Arduino Uno, the FQBN is `arduino:avr:uno`.

**2. Install the core**
Using the prefix from the FQBN (in this case, `arduino:avr`), install the core files needed to compile code for that board:
```bash
arduino-cli core install arduino:avr
```

---

### **Step 4: Your First Workflow (Create, Compile, Upload)**

Now that it's configured, here is how you use it day-to-day.

**1. Create a new sketch**
```bash
arduino-cli sketch new MyBlink
```
This creates a folder named `MyBlink` containing a `MyBlink.ino` file with empty `setup()` and `loop()` functions.

**2. Compile the sketch**
Pass the FQBN of your board using the `-b` flag:
```bash
arduino-cli compile -b arduino:avr:uno MyBlink
```

**3. Upload to the board**
Pass the FQBN (`-b`) and the specific Port (`-p`) where your Arduino is connected (found earlier using `board list`):
```bash
# On Mac/Linux (port will look like /dev/ttyACM0 or /dev/cu.usbmodem14101)
arduino-cli upload -p /dev/ttyACM0 -b arduino:avr:uno MyBlink

# On Windows (port will look like COM3)
arduino-cli upload -p COM3 -b arduino:avr:uno MyBlink
```

---

If you prefer using MacPorts over Homebrew, the process is just as straightforward! 

Assuming you already have MacPorts installed and your port trees are synced, you can install the CLI with a single command.

Open your terminal and run:
```bash
sudo port install arduino-cli
```

### **Useful MacPorts Commands for Arduino-CLI**

* **Check the installed files:**
    ```bash
    port contents arduino-cli
    ```
* **Keep it updated:**
    To upgrade the CLI to the latest version in the future, run:
    ```bash
    sudo port selfupdate && sudo port upgrade arduino-cli
    ```

Once it finishes installing, you can verify it by running `arduino-cli version`, and then proceed with the `arduino-cli config init` and `core update-index` steps just like normal!