# Standard 068: Tag Infection & Weak Supervision Protocol

## 1. The Core Philosophy
**"Discover with the LLM, Infect with the CPU."**

The objective is to achieve semantic organization across millions of atoms without the prohibitive cost of LLM-processing for every unit. This is achieved via a **Teacher-Student** architecture where the LLM (Teacher) discovers rules that a high-speed NLP/Regex engine (Student) applies at scale.

## 2. The Discovery Mode (The Scout)
The Engine samples the dataset to identify "Patient Zero" patterns.

- **Sampling**: Query a small, diverse subset of atoms (e.g., 20-100 atoms per bucket).
- **Extraction**: The LLM (e.g., GLM 1.5B) extracts high-entropy entities, relationship markers, or topical keywords.
- **Rule Generation**: The extracted entities are transformed into a **Master Tag List** (The Virus).

## 3. The Infection Mode (The Swarm)
The Engine applies the Master Tag List to the entire database at CPU speeds.

- **Engine**: Uses a high-performance NLP library (e.g., `wink-nlp`) or optimized Regex.
- **Protocol**: 
  1. Load the Master Tag List into memory.
  2. Stream atoms from the database.
  3. Perform string-match or dependency-match for Master Tags.
  4. "Infect" matching atoms by appending the discovered tags to their `tags` array.
- **Performance**: Targeting >10,000 atoms per second per core.

## 4. The Weak Supervision Loop
This is a semi-automated feedback loop.

1. **Discovery**: LLM finds "Dory" is an entity of type `#family`.
2. **Infection**: All atoms containing "Dory" are tagged `#family`.
3. **Verification**: User audits a subset of infected atoms.
4. **Correction**: If "Dory" also refers to a "fish", the system refines the rule to `Dory AND Jade` -> `#family`.

## 5. Metrics
- **Recall**: Percentage of tags discovered via sampling vs exhaustive LLM scan.
- **Precision**: Accuracy of CPU-based infector compared to LLM-based tagging.
- **Throughput**: Atoms processed per second.
