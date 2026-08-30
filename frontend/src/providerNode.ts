// Qual provedor um nó da cena representa — e, portanto, qual credencial ele configura.
//
// **Só o nó canônico configura.** A cena tem dois nós por provedor: o da nuvem de
// provedores, que vem da projeção (`op/provider/<nome>`), e o da camada viva, que nasce
// da trilha (`runtime:provider:<nome>`). Eles apontam para a mesma credencial, mas
// dizem coisas diferentes: o primeiro é o provedor como cadastro — chave, catálogo,
// disponibilidade —, e o segundo é o provedor **naquela execução**, que já terminou ou
// ainda está aberta. Abrir campo de chave sobre um passo de raciocínio ofereceria
// configurar o passado.
//
// Módulo próprio porque `main.ts` monta a aplicação ao ser importado: uma função pura
// morando lá não teria como ser testada sem instanciar DOM, atlas e WebGL.

const PREFIXOS = ['op/provider/'] as const;

/**
 * O provedor por trás de um nó, ou `null` quando o nó não configura credencial.
 *
 * Recusar é o caso comum: nota, evento, modelo, painel de quórum — e o provedor da
 * camada viva — não configuram credencial nenhuma, e abrir a configuração sobre eles
 * afirmaria um vínculo inexistente ou ofereceria configurar uma execução.
 */
export function providerIdOf(nodeId: string | null | undefined): string | null {
  if (!nodeId) return null;
  for (const prefixo of PREFIXOS) {
    if (!nodeId.startsWith(prefixo)) continue;
    const nome = nodeId.slice(prefixo.length).trim();
    // O nó do modelo começa com `runtime:model:` e não cai aqui; mas um id de provedor
    // com barra significaria um endpoint colado no nome, e configurar "groq/qwen" não
    // existe: a chave é do provedor.
    if (nome === '' || nome.includes('/')) return null;
    return nome;
  }
  return null;
}

const PREFIXO_TRABALHADOR = 'op/worker/';

/**
 * O papel do trabalho por trás de um nó, ou `null` quando o nó não é de um.
 *
 * Papel tem nó próprio desde que a configuração dele virou painel. Antes disso, os
 * sete só apareciam na cena como votos dentro de centenas de painéis de quórum — um
 * voto é a execução de um papel, não o papel.
 */
export function workerIdOf(nodeId: string | null | undefined): string | null {
  if (!nodeId || !nodeId.startsWith(PREFIXO_TRABALHADOR)) return null;
  const nome = nodeId.slice(PREFIXO_TRABALHADOR.length).trim();
  return nome === '' || nome.includes('/') ? null : nome;
}
