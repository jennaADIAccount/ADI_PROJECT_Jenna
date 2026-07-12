# Why Figures aren't Essential for vPlan Generation:
### This document addresses the high-risk figure capturing feature of the extractor.

* There's enough context and explanation before and after the figures in the RISC-V ISA protocol specification and the AMBA AXI specification.
### This is seen in both specifications in the examples below:
* **AMBA AXI:** The timing diagrams illustrating the **VALID/READY handshake** are supported by the surrounding text, which explicitly states the handshake rules (e.g., transfers occur only when both `VALID` and `READY` are asserted, and signal stability requirements while waiting). The figure simply visualises one example of behaviour already fully defined in the text.

* **AMBA AXI:** Burst transaction waveforms (read/write bursts) are accompanied by textual descriptions of burst types, transfer ordering, burst length, and response rules. These paragraphs define all legal protocol behaviour, whereas the figures only show representative examples.

* **RISC-V ISA:** Instruction format diagrams (showing fields such as `opcode`, `rd`, `rs1`, `rs2`, and `funct3`) duplicate information already provided in the encoding tables and instruction descriptions. The tables contain all the information needed for extracting instruction encodings.

* **RISC-V ISA:** CSR layouts and register diagrams are reinforced by accompanying tables and descriptive text that define each field's purpose, encoding, and behaviour. The textual definitions are sufficient for understanding and extracting the architectural requirements without relying on the diagrams.

* OCR text is extracted and provides sufficient explanation.

* Figures are used to convey the requirements and essential information needed for vPlan generation.

* **Normative information is contained in text, not figures.** Both the **AMBA AXI** and **RISC-V ISA** specifications define protocol behaviour, constraints, instruction semantics, and requirements through textual descriptions, tables, and field definitions. Figures are primarily provided to aid understanding.

* **Figures are illustrative rather than exhaustive.** Timing diagrams and architecture diagrams show example transactions or layouts, whereas the accompanying text specifies all legal behaviours, corner cases, and constraints needed for verification.

* **Verification plans are derived from requirements, not graphics.** VPlan generation relies on extracting protocol rules, signal definitions, instruction semantics, encodings, and exception behaviour, all of which are explicitly documented in text and tables.

* **Tables provide structured, machine-readable information.** Signal descriptions, opcode encodings, register fields, response codes, and protocol attributes can be directly extracted from tables without interpreting figures.

* **Figures add complexity with limited additional value.** Processing figures requires OCR and diagram interpretation, while the same information is typically available in the surrounding text. This increases processing effort without significantly improving the extracted verification content.

### **Conclusion:** 
For both the **AMBA AXI** and **RISC-V ISA** specifications, a text-first extraction approach captures the information required for VPlan generation. Figures are useful for human comprehension but are not essential for extracting verification requirements.


