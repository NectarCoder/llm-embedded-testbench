# Project Midterm Report: Structured Prompting and Automated Self-Debugging for LLM-Based Embedded Code Generation

{authors redacted}

## Abstract
While Large Language Models (LLMs) have demonstrated remarkable potential in general software generation, their application to embedded systems development remains hampered by low first-attempt correctness and a heavy reliance on human-mediated debugging. Current research emphasizes the qualitative benefits of human-AI co-development, but it lacks a formal characterization of how structured prompting and automated feedback loops independently influence generated code reliability. In this work, we propose an enhanced hardware-in-the-loop (HIL) framework designed to transform the manual, one-shot firmware generation pipeline into a semi-autonomous, closed-loop development environment. Our approach integrates newer state-of-the-art models, including Gemini 3.1, Claude 4.6, and GPT 5.4, as well as privacy-centric local LLMs such as Llama 4, DeepSeek R1, with an automated self-debugging mechanism that programmatically feeds compiler errors and the hardware constraints back into the model for iterative refinement. We evaluate the proposed framework using an Arduino Mega 2560 testbench across five benchmark tasks of increasing complexity, ranging from basic serial communication, to I2C-based sensor fusion, and low-power interrupt management. By isolating the prompt structure, and automated error-driven feedback as experimental variables, we aim to quantify their impact on the functional output correctness and the reduction of human intervention.

**Keywords:** Large Language Models, Prompt Engineering, Automated Debugging, Embedded Systems, Code Generation, Software Reliability, Human-AI Collaboration

---

## 1 Introduction

### 1.1 Project Objective
The primary objective of our project is to transform the manual, one-shot LLM firmware generation pipeline from the original source into a semi-autonomous, closed-loop development environment. By utilizing adaptive automation, we aim to reduce the frequency and complexity of human intervention, thereby making embedded systems development more accessible to non-experts while enhancing efficiency and consistency for seasoned engineers. This approach emphasizes improved accuracy, higher code quality, and greater consistency in embedded code generation. Our effort seeks to offer a more cohesive, streamlined, and intelligent assistant framework that can perform LLM-powered code generation in an embedded software development environment.

### 1.2 Problem Statement
The paper acknowledges that "effective prompting is crucial" and provides high-level usage suggestions in Appendix A, such as supplying detailed hardware descriptions and copying compiler errors back to the model. In the user study, participants performed better when provided with workflow guidance for interacting with GPT-4. However, the author's methodology does not systematically compare prompt structures, evaluate alternative prompt formats, or quantify how specific prompting strategies can influence compilation success or functional correctness. The provided guidance to the participants is general advice, rather than as a controlled experimental variable. Consequently, while the importance of prompting is demonstrated qualitatively, there is no formal characterization of how structured prompt design affects embedded code reliability.

Another gap in relation to this is iterative debugging; in the study, it is entirely human-mediated. Participants manually copied compiler errors or behavioral descriptions into GPT-4 and iteratively refined the code until correct behavior was achieved. The automated physical testbench introduced in the paper evaluates single-shot code generation across 450 trials, but it does not implement automated compile-feedback repair cycles. In other words, while the paper's testbench implementation measures the correctness of model outputs, it does not incorporate self-correction loops in which compiler errors are programmatically fed back to the model. Both of these issues combined presents a measurable methodological gap.

The paper does mention that prompting quality influences performance and that iterative debugging improves the generated code outcomes. Additionally, the first-attempt correctness is often low for complex tasks; for instance, GPT-4 achieving full correctness only 16% of the time on the IMU (Inertial Measurement Unit) task. However, it did not evaluate whether structured prompt design and automated error-driven refinement can independently improve the reliability, independent of continuous human intervention. As a result, the reliability limits of LLM-generated embedded code remain incompletely characterized. It can become unclear whether the observed productivity gains stem primarily from model capability, human expertise in prompt crafting, iterative error interpretation, or the interaction between these factors. Only by isolating and formalizing these components, the reliability and accuracy of LLM-assisted code generation in embedded software development can be more concretely determined.

---

## 2 Background

### 2.1 Status of Current Research
Our project is focused on extending the work of Englhardt, et. al [2]. This work was an empirical study, focused on discovering how programmers are able to use LLMs to accomplish tasks in an embedded systems design space. Researchers from the University of Washington developed a hardware-in-the-loop (HIL) framework to evaluate the performance of code generated by GPT-4 and PaLM-2, both of which were tasked with producing firmware for microcontroller-based applications. The framework enabled automated testing of generated code (with human oversight) on a virtual emulation of the hardware, then ultimately on the hardware itself.

The study examined how programmers interacted with these LLMs in a human-AI co-development workflow. The humans participating in the user study were given a series of five tasks designed to mimic assignments from an introductory embedded systems class. The participants were given varying access to the models, ranging from no-access to access with specific guidelines provided by the researchers themselves. After each task, the participants were surveyed on their experience, and the authors observed that even when generated code failed, the models often produced useful reasoning and debugging suggestions, which supported the users in iterative development. After their study, the authors provided an open-source version of their testbed, which can be found at: [https://github.com/anonimwut/llm-embedded-testbench](https://github.com/anonimwut/llm-embedded-testbench).

---

## 3 Design
Our proposed design extends the evaluation pipeline introduced by Englhardt et al. [2] by enhancing the existing hardware-in-the-loop testbench with newer large language models, automated feedback mechanisms, and improved prompting strategies. We believe the original pipeline is limited by its reliance on human intervention; while we do not advocate for removing the human from the loop entirely, we aim to minimize manual intervention where possible. To address these limitations, we propose the following three key enhancements.

### 3.1 Integration of Newer and Offline-Capable Models
We will evaluate newer state-of-the-art LLMs, specifically, Gemini 3.1, Claude 4.6, and GPT 5.4 to explore whether modern models improve code correctness and hardware awareness. These models represent the current frontier of reasoning capabilities based on newer training data, better model architectures, and larger context window management. Furthermore, to address the privacy and connectivity requirements of industrial embedded development, we will investigate the performance of locally deployable frontier-class models, perhaps including model such as Llama 4 and DeepSeek R1. A local model may benefit users in privacy-sensitive or disconnected environments and could be paired with Retrieval-Augmented Generation (RAG) strategies, such as providing device manuals and hardware documentation directly to the model. This direction further extends the authors' original vision of an automated physical testbench by reducing dependencies such as continuous internet connectivity. It is to be noted we are still working on integrating RAG functionality in context with the local-based models.

### 3.2 Prompt engineering and Structured Context
We will develop improved prompting strategies that incorporate structured task descriptions, hardware constraints, and feedback from prior iterations. Prompt templates will include context such as device specific pin mappings, timing requirements, and memory limits. This approach aims to reduce non-deployable code and improve reliability across repeated trials.

Our testing evaluation between prompts will vary based on a key difference a simple 'ask-based' prompt, and a structured desired output prompt, where an engineer will detail exactly what they want by defining multiple constraints and parameters, such as, hardware setup, architecture, intended correct output, etc. A good example of a simple ask-based prompt would be: 

> 'I would like my Arduino to display text on a HUD'. 

Whereas a structured prompt would appear more similar to the following: 

> "Design an Arduino-based system to render alphanumeric text on a heads-up display (HUD) using an <insert display module type>. The system must operate on an <Arduino type>. The output should initialize the display, render a static string ("HELLO") centered on the screen, and provide a modular function for updating displayed text. Include complete, deployable code with clear pin configuration, setup/loop structure, and comments describing timing and memory considerations." 

### 3.3 Comparative Evaluation and Task Adaption
We will be using our own Arduino hardware setup, and emulating the original tasks to the best of our ability. While some compromises may have to be made based on hardware ability, we intend to maintain the spirit of the original paper's tasks. We will pair this hardware setup with the authors' open-source testbench, and compare our enhanced pipeline against the original workflow using the original metrics provided by the authors, including task completion time, functional correctness, number of repair iterations, and degree of human intervention required. This evaluation will determine whether tighter feedback integration and newer models enable programmers to complete embedded development tasks more quickly and accurately.

---

## 4 Methodology

### 4.1 Implementation
We have begun implementing modification on the open-source testbench provided by [2]. We have obtained an Arduino ATmega2560, which replaces the Arduiono Uno used in the original study. The Mega 2560 offers a larger flash memory, more SRAM, and a higher pin count, providing plenty headroom for recreating the character of the development tasks. Because the ATmega2560 is well-represented in Arduino documentation, we expect that the LLMs we are evaluating will have comparable exposure to the board relative to the Uno, and that baseline performance differences attributable to board familiarity will be minimal. Our peripheral set was assembled from a commercially available starter kit, and the selection of components was guided by the goal of approximating the five benchmark tasks defined by Englhardt et al. as closely as possible within a constrained budget.

### 4.2 Evaluation Metrics
Our evaluation strategy has two complementary components: qualitative and quantitative. We plan on gathering numerical results of metrics such as LLM token usage, response time, overall experiment completion time, etc. As for qualitative measures, we assess each model's overall suitability for the embedded development context. This includes relevance and correctness of the reasoning provided alongside generated code, knowledge retrieval accuracy, and what LLM evaluation literature (and the greater lexicon of pop-culture) have begun to formalize as the model vibes [1]. This is the aggregate impression of how naturally and productively a developer can collaborate with a given model. While this is an informal name, this measure reflects a genuine and important dimension of human-AI collaboration. These metrics will help us to compare model aptitude and choose the best fit for our modified testbench.

---

## 5 Experiments
To evaluate the performance of our modified testbench in its ability to bridge the gap between AI models and human developers in an embedded systems development environment, we have designed multiple experiments to garner results that we can compare to the original paper using our available hardware. Because our component set was assembled under budget constraints, several tasks required substantive substitutions; we document these explicitly so that the spirit of each task is preserved even where the hardware differs. Our hypothesis is that structured prompting combined with automated error-driven feedback will meaningfully increase attempts and reduce the number of repair iterations required to reach correctness.

### 5.1 Summary of Task Adaptations
Table 1 summarizes the mapping between the original tasks and our adapted versions, along with the primary compromises introduced by our hardware constraints. Where compromises are significant, we aim to have the adapted tasks measure a similarly sophisticated task. Results for these tasks will be interpreted accordingly and not directly compared to the original paper's figures without qualification.

| Original Task | Original Hardware | Substituted Hardware | Notes |
| :--- | :--- | :--- | :--- |
| Warm-up | LED+Serial | LED+Serial | Identical - No compromise |
| Environmental Sensor | BME280 + LoRa radio pair | DHT11 (temp/humidity) + HC-SR04 | No wireless - Significant Compromise |
| Heart Rate Monitor | PPG + BLE (nRF52) | ADXL345 accelerometer | No BLE - Significant Compromise |
| Timer Interrupt | Piezo buzzer | Passive buzzer | Nearly identical - Low compromise |
| RTC Wakeup | PCF8523 RTC Module + sleep | DS3231 RTC Module + sleep | Nearly drop-in - Low compromise |

*Table 1: Overview reference for experiment recreations.* *(Note: Table reconstructed contextually from document text.)*

### 5.2 Task 1 - Warm-Up: Serial Print and LED Blink
**Original Task:** Print "Hello, World!" to Serial Console, and also have an LED blink.
**Our implementation:** This task maps directly onto our hardware with no meaningful compromise. We will have the user write firmware for the Mega 2560 that prints a greeting string to the Serial monitor, and then toggle a blue LED at a 1 Hz rate.

### 5.3 Task 2 - Environmental Sensor
**Original Task:** Connect an environmental sensor and transmit sensor readings to another arduino over long range (LoRa) radio waves.
**Our implementation:** This task is going to require significant compromise in our replication. We do not have access to a LoRa radio module or a second microcontroller, so the wireless transmission component cannot be reproduced. Instead, we rescope the task to sensor acquisition. The user is prompted to interface with the DHT11 temperature and humidity sensor and the HC-SR04 ultrasonic distance sensor, and to print readings for both peripherals to the Serial monitor. We believe the sophistication of this task will be sufficient for challenging users.

### 5.4 Task 3 - Heart Rate Monitor
**Original Task:** Connect a photoplethysmography (PPG) sensor to a nRF52 and transmit sensor readings to a second nRF52 over bluetooth.
**Our implementation:** This task requires a deep departure from the original design as we have neither a BLE-capable microcontroller nor a PPG sensor. Instead, we plan to require the user to use the ADXL345 over I2C and read the X, Y, and Z acceleration values at a specific sampling rate. This substitution preserves several key challenges from the original task such as correct I2C initialization, use of a sensor-specific library, and interpretation of raw register data.

### 5.5 Task 4 - Timer Interrupt
**Original Task:** generate a particular tone (440 hx) using a piezoelectric buzzer.
**Our implementation:** This task maps closely to our hardware. We are using a passive buzzer, which will require timer configuration rather than a trivial signal.

### 5.6 Task 5 - RTC Wakeup
**Original Task:** Wake an Arduino from sleep mode, flash an LED, and return to sleep, all using a real time clock (PCF8523).
**Our implementation:** We will use a DS3231 RTC module as a drop-in functional replacement for the PCF8523. Both devices communicate over I2C and expose a configurable alarm output pin that can be used to trigger an external interrupt on the microcontroller. The user will be prompted to configure the alarm, place the Mega 2560 in power-down sleep mode, wake on the RTC interrupt, and flash a red LED before returning to sleep.

---

## References
[1] Lisa Dunlap, Krishna Mandal, Trevor Darrell, Jacob Steinhardt, and Joseph E Gonzalez. 2025. VibeCheck: Discover and Quantify Qualitative Differences in Large Language Models. arXiv:2410.12851 [cs.CL] [https://arxiv.org/abs/2410.12851](https://arxiv.org/abs/2410.12851)  
[2] Zachary Englhardt, Richard Li, Dilini Nissanka, Zhihan Zhang, Girish Narayanswamy, Joseph Breda, Xin Liu, Shwetak Patel, and Vikram Iyer. 2024. Exploring and characterizing large language models for embedded system development and debugging. In Extended Abstracts of the CHI Conference on Human Factors in Computing Systems. 1-9.

*(Note: Page headers and footers from the raw text layout have been omitted for readability.)*