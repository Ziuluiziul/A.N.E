/**
 * Quem ganha o clique quando a nota e o painel vivo ocupam o mesmo raio.
 *
 * Cinco notas do observatório recente têm dois painéis no anel: o raio acerta as
 * duas placas e a nota, maior, ficava com o clique. A camada operacional é a
 * placa da frente daquele anel; a nota continua selecionável onde o painel não
 * cobre.
 */

export function escolherAlvoDoClique(
  corpus: { entityId: string } | null,
  operacional: { entityId: string } | null,
): { entityId: string; runtime: boolean } | null {
  if (operacional) return { entityId: operacional.entityId, runtime: true };
  if (corpus) return { entityId: corpus.entityId, runtime: false };
  return null;
}
