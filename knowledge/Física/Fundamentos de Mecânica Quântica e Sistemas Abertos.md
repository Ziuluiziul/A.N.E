---
title: Fundamentos de Mecânica Quântica e Sistemas Abertos
domain: física
kind: nota
status: active
epistemic_status: established
updated: 2026-08-30
verified_at: 2026-07-16
---

# Fundamentos de mecânica quântica e sistemas abertos

## Escopo

Base mínima para separar superposição, emaranhamento, decoerência, medição e modelos de colapso objetivo.

## 1. Estados e observáveis

Um estado puro é um raio `|ψ⟩` em um espaço de Hilbert. Estados estatísticos são operadores densidade

$$
\rho\ge0,\qquad \operatorname{Tr}\rho=1.
$$

Para observável autoadjunto `A`,

$$
\langle A\rangle=\operatorname{Tr}(\rho A).
$$

Uma medição geral é descrita por uma POVM `{E_k}`, com `E_k≥0`, `Σ_kE_k=I` e probabilidade de Born `p(k)=Tr(ρE_k)`.

## 2. Evolução fechada

Para sistema fechado,

$$
i\hbar\frac{d}{dt}|\psi\rangle=H|\psi\rangle,
\qquad
\dot\rho=-\frac{i}{\hbar}[H,\rho].
$$

A evolução é unitária e preserva pureza. Uma redução objetiva da função de onda não decorre dessa equação; precisa ser um postulado interpretativo ou modificação dinâmica.

## 3. Sistemas compostos e emaranhamento

Para `\mathcal H_A\otimes\mathcal H_B`, o estado reduzido é

$$
\rho_A=\operatorname{Tr}_B\rho_{AB}.
$$

Um estado puro global pode produzir estado reduzido misto. Emaranhamento é correlação quântica não separável; não autoriza sinalização superluminal nem implica, sozinho, coerência funcional macroscópica.

## 4. Decoerência

Interação com um ambiente correlaciona graus de liberdade do sistema e do ambiente. Na base selecionada pela interação, termos fora da diagonal de `ρ_S` podem ser suprimidos:

$$
\rho_S(t)=\operatorname{Tr}_E\! \big[U(t)\rho_{SE}(0)U^\dagger(t)\big].
$$

Decoerência explica a perda local de interferência e a emergência de bases aproximadamente clássicas. Ela não seleciona, por si só, um único resultado global; por isso não é sinônimo de colapso objetivo.

## 5. Dinâmica de Lindblad

Sob aproximações markovianas e uma dinâmica completamente positiva e preservadora do traço,

$$
\dot\rho=-\frac{i}{\hbar}[H,\rho]+
\sum_k\left(L_k\rho L_k^\dagger-
\frac12\{L_k^\dagger L_k,\rho\}\right).
$$

Os operadores `L_k` codificam canais efetivos. Ajustar uma equação de Lindblad não prova o mecanismo microscópico: Markovianidade, coarse graining e parâmetros devem ser testados.

## 6. Escalas e experimentos

Um “tempo de decoerência” depende do estado, observável, acoplamento, temperatura e ambiente. Não existe um tempo universal de coerência para “o cérebro” ou “o microtúbulo”. Evidência de emissão coletiva, transporte excitônico ou rendimento quântico não demonstra automaticamente qubits biológicos nem consciência quântica.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-QM-001` | Regra de Born, evolução unitária e matriz densidade formam o núcleo operacional da mecânica quântica. | `established` | Formalismo confirmado em múltiplas plataformas experimentais. |
| `CLM-FIS-QM-002` | Decoerência suprime interferência local em bases selecionadas pelo ambiente. | `established` | Zurek e Schlosshauer; depende de estado, acoplamento e ambiente. |
| `CLM-FIS-QM-003` | Decoerência, sozinha, seleciona um único resultado global. | `open` | Não decorre apenas do traço parcial; depende da interpretação da medição. |
| `CLM-FIS-QM-004` | Uma equação de Lindblad descreve qualquer ambiente. | `refuted` | Lindblad pressupõe uma classe de dinâmicas completamente positivas e, usualmente, aproximações markovianas. |
| `CLM-FIS-QM-005` | A gravidade produz colapso objetivo. | `hypothesis` | Sem confirmação experimental; distingue-se de decoerência ambiental. |

## Relações justificadas

- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:prerequisite --> fornece Hilbert, operadores, probabilidade e EDPs.
- [[Colapso Objetivo, Decoerência e Biofísica Quântica]] <!-- relation:extends --> aplica essas distinções a Diósi–Penrose, Orch-OR e microtúbulos.
- [[Termodinâmica de Buracos Negros e Informação]] <!-- relation:extends --> usa entropia de emaranhamento e sistemas quânticos abertos.
- [[Fundamentos de Teoria Quântica de Campos e Teorias Efetivas]] <!-- relation:extends --> generaliza o formalismo para campos relativísticos.
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Göran Lindblad, “On the Generators of Quantum Dynamical Semigroups”, *Communications in Mathematical Physics* 48, 119–130 (1976), DOI `10.1007/BF01608499`.
- Wojciech H. Zurek, “Decoherence, einselection, and the quantum origins of the classical”, *Reviews of Modern Physics* 75, 715–775 (2003), DOI `10.1103/RevModPhys.75.715`, arXiv:`quant-ph/0105127`.
- Maximilian Schlosshauer, “Decoherence, the measurement problem, and interpretations of quantum mechanics”, *Reviews of Modern Physics* 76, 1267–1305 (2005), DOI `10.1103/RevModPhys.76.1267`, arXiv:`quant-ph/0312059`.
