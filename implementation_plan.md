# Plano Único de Implementação — Finance Tracker

Este plano unifica:

1. correções críticas de integridade e segurança;
2. reorganização de UX do produto;
3. reformulação visual mobile-first;
4. validação incremental para não quebrar funcionalidades existentes.

O princípio central é simples: primeiro estabilizar comportamento e nomenclatura financeira; depois criar a fundação visual; só então migrar cada tela, uma por vez.

---

## Hotfix imediato (fora do plano principal)

Este item não deve esperar as etapas maiores, porque corrige um crash objetivo.

### H1 — Import faltante de `analisar_sazonalidade()`

**Arquivo**

- [views/tab_historico.py](views/tab_historico.py)

**Problema**

O bloco de sazonalidade chama `analisar_sazonalidade()` sem importar a função. Usuários com histórico suficiente podem quebrar a aba `📈 Evolução Histórica`.

**Mudança**

Adicionar o import faltante e validar a aba com 6+ meses.

**Critério de aceite**

A aba histórica não quebra mais por `NameError`.

---

## Objetivo de produto

Ao final da implementação, o usuário deve conseguir:

1. entender em menos de 5 segundos a situação do ciclo atual;
2. identificar claramente a próxima ação necessária;
3. confiar na leitura dos números, sem ambiguidade entre valor real e projetado;
4. usar a aplicação em mobile sem layout quebrado, sem depender de correções posteriores.

---

## Guardrails de implementação

1. Não misturar refatoração visual ampla com mudança de regra de negócio na mesma etapa, exceto onde a semântica financeira exigir.
2. Não alterar `session_state`, chaves, payloads de persistência ou contratos de `DataService` sem necessidade objetiva.
3. Toda nova camada visual deve nascer em viewport mobile e ser ampliada com `min-width`, nunca o contrário.
4. Nenhuma etapa está concluída sem validação explícita em mobile antes do ajuste desktop.
5. Cores devem comunicar significado; decoração nunca pode competir com estado financeiro.
6. Números monetários devem usar alinhamento à direita e `tabular-nums`.
7. Ações destrutivas devem passar pela camada de serviço adequada e exigir confirmação deliberada.
8. Cada informação importante deve ter uma superfície principal; repetição em outra superfície só é permitida se houver mudança clara de contexto.
9. Hero, alertas, KPIs, resumo e tabelas não podem repetir a mesma mensagem no mesmo nível de detalhe.
10. Não usar fonte, cor, badge, ícone ou animação para compensar falta de hierarquia informacional.

### Regra editorial obrigatória: uma informação, uma superfície principal

Cada fato relevante do produto deve ter um local primário de leitura:

| Tipo de informação | Superfície principal |
|---|---|
| decisão imediata do ciclo | hero card |
| ação necessária | fila de ações / callouts |
| número-chave do mês | KPI |
| composição e auditoria | resumo / tabela |
| detalhe operacional | expander ou dataframe |
| tendência ao longo do tempo | gráfico ou tabela histórica |

Regras de aplicação:

1. Se um valor já está em um KPI, o resumo abaixo não deve repeti-lo integralmente, a menos que mude a pergunta respondida.
2. Alertas não devem duplicar o texto do hero; devem informar ação, risco ou exceção.
3. Um mesmo conjunto de itens não pode aparecer em duas listagens completas consecutivas.
4. Gráficos e tabelas que usam a mesma base precisam responder perguntas diferentes.
5. Quando houver conflito entre densidade e repetição, remover repetição primeiro.

---

## Linguagem visual alvo

### Direção

O dashboard deve migrar de uma estética de "fintech chamativa" para uma estética de "ledger calmo":

- menos glow, menos gradiente, menos peso dramático;
- mais clareza, mais contraste útil, mais hierarquia de informação;
- sensação de banco premium e confiável, não de painel genérico de growth.

### Paleta base

#### Light

| Token | Valor |
|---|---|
| `bg.canvas` | `#F7F7F3` |
| `bg.surface` | `#FFFFFF` |
| `bg.surface_alt` | `#F2F4EF` |
| `bg.surface_emphasis` | `#EDEAE1` |
| `border.subtle` | `#E7E4DB` |
| `border.strong` | `#D6D1C4` |
| `text.primary` | `#16181D` |
| `text.secondary` | `#667085` |
| `text.subtle` | `#8A8F98` |
| `brand.primary` | `#0F766E` |
| `brand.soft` | `#DDF3EF` |
| `info` | `#2563EB` |
| `info.soft` | `#DBEAFE` |
| `success` | `#15803D` |
| `success.soft` | `#DCFCE7` |
| `warning` | `#B45309` |
| `warning.soft` | `#FEF3C7` |
| `danger` | `#B42318` |
| `danger.soft` | `#FEE4E2` |

#### Dark

O dark mode deve ser preservado, mas derivado semanticamente do light, não redesenhado como um tema separado.

| Token | Valor |
|---|---|
| `bg.canvas` | `#111318` |
| `bg.surface` | `#171A20` |
| `bg.surface_alt` | `#1E232B` |
| `bg.surface_emphasis` | `#232A33` |
| `border.subtle` | `#2B313C` |
| `border.strong` | `#3A4352` |
| `text.primary` | `#F3F4F6` |
| `text.secondary` | `#98A2B3` |
| `text.subtle` | `#7C8798` |
| `brand.primary` | `#2DD4BF` |
| `brand.soft` | `rgba(45,212,191,.14)` |
| `info` | `#60A5FA` |
| `success` | `#4ADE80` |
| `warning` | `#FBBF24` |
| `danger` | `#F87171` |

### Tipografia

Fonte principal recomendada:

- `Manrope Variable`, fallback `system-ui, sans-serif`

Regras:

1. usar `font-variant-numeric: tabular-nums lining-nums;` para valores;
2. reduzir uso de uppercase para labels realmente auxiliares;
3. evitar tracking exagerado em seções e KPIs.
4. usar no máximo 3 pesos de fonte na interface corrente;
5. evitar pesos extremos em blocos densos como tabelas, dataframes e formulários longos.

### Regras de uso tipográfico

1. `Manrope` é a fonte padrão de toda a interface.
2. Tabelas, dataframes, filtros e telas operacionais devem priorizar legibilidade, não personalidade visual.
3. Em conteúdo denso, preferir `500` e `600`; reservar `700` para destaque pontual.
4. Evitar `800+` fora do KPI hero.
5. Uppercase só em labels auxiliares curtas; não usar uppercase em títulos longos ou explicações.
6. Não usar letter-spacing alto em mobile.
7. Todos os valores monetários, percentuais e deltas devem usar números tabulares.

Escala tipográfica:

| Uso | Mobile | Desktop |
|---|---|---|
| Título da página | `28/32` | `34/40` |
| Título de seção | `18/24` | `20/26` |
| Texto base | `14/20` | `14/20` |
| Label de card | `12/16` | `12/16` |
| Caption | `12/16` | `12/16` |
| KPI normal | `28/32` | `36/40` |
| KPI hero | `44/48` | `56/60` |

### Espaçamento, raio e elevação

1. Grid base de `8px`.
2. Padding lateral:
   `16px` mobile, `24px` tablet, `32px` desktop.
3. Radius:
   `12px` em cards comuns, `16px` em hero cards.
4. Sombra:
   mínima, só para separação de superfície; sem glow decorativo.

### Cores semânticas obrigatórias

| Papel | Cor |
|---|---|
| informação/progresso | azul |
| sucesso/estável | verde |
| atenção | âmbar |
| erro/risco crítico | vermelho |
| neutro/apoio | cinza |

Cor de accent não pode substituir cor semântica.

---

## Regras mobile-first

### Breakpoints

Implementar CSS progressivo usando `min-width`:

| Faixa | Largura | Objetivo |
|---|---|---|
| Base | `0–480px` | iPhone padrão, implementação principal |
| Tablet | `481–768px` | ganho de densidade controlado |
| Desktop | `769–1279px` | expansão horizontal |
| Wide | `1280px+` | refinamento, nunca dependência |

### Regras de layout

1. Toda tela deve funcionar bem em `393x852` antes de receber ajustes para desktop.
2. Base mobile deve ser empilhada em uma coluna.
3. KPIs:
   `1 coluna` no mobile base, `2 colunas` no tablet, `4 colunas` apenas no desktop.
4. Nenhum bloco pode depender de `hover` para revelar informação importante.
5. Alvos interativos mínimos de `44px`.
6. Overflow horizontal só é permitido para:
   tabelas densas, dataframes e alguns gráficos específicos.
7. Tabs devem ser testadas explicitamente em mobile; se o rótulo quebrar leitura, encurtar o texto globalmente.
8. Em mobile, priorizar ordem de leitura sobre simetria visual.
9. Nenhuma tela pode depender de duas colunas para fazer sentido.

### Regra de aceitação de UI

Uma etapa visual não passa se houver qualquer um destes sintomas em mobile:

1. truncamento de título/KPI sem tratamento;
2. badge ou botão menor que `44px`;
3. tabela ilegível sem scroll controlado;
4. gráfico cujo texto invada outro componente;
5. ação crítica escondida em layout colapsado.

---

## Estratégia para não quebrar funcionalidades

1. Executar a implementação em fatias pequenas e mergeáveis.
2. Preservar classes CSS antigas durante a migração; remover legado só depois de todas as views adotarem a nova camada.
3. Não trocar simultaneamente o tipo de visualização e a fonte dos dados do mesmo componente.
4. Em `tab_raiox.py`, separar primeiro:
   semântica financeira, depois estrutura, depois estética.
5. Em `tab_settings.py`, priorizar hardening do fluxo antes da reorganização visual.

---

## Sequência única de implementação

## Etapa 0 — Baseline, inventário e prova de não regressão

**Objetivo**

Criar uma linha de base antes de qualquer alteração estrutural.

**Arquivos**

- [app.py](app.py)
- [views/styles.py](views/styles.py)
- [views/tab_raiox.py](views/tab_raiox.py)
- [views/tab_historico.py](views/tab_historico.py)
- [views/tab_importacao.py](views/tab_importacao.py)
- [views/tab_settings.py](views/tab_settings.py)
- [views/onboarding.py](views/onboarding.py)

**Ações**

1. Registrar screenshots atuais em `393px`, `768px` e `1440px`.
2. Mapear os fluxos críticos:
   `Raio-X`, histórico com 6+ meses, importação por imagem, edição manual, exclusão de mês, onboarding.
3. Confirmar a suíte mínima de teste a executar ao longo do trabalho.

**Critério de aceite**

Existe checklist visual e funcional do estado atual para comparação.

---

## Etapa 1 — Hardening funcional e semântico

**Objetivo**

Eliminar riscos de dado, exclusão, crash e nomenclatura enganosa antes da mudança visual.

**Arquivos**

- [views/tab_settings.py](views/tab_settings.py)
- [views/tab_raiox.py](views/tab_raiox.py)
- [views/onboarding.py](views/onboarding.py)
- [services/data_service.py](services/data_service.py)
- [services/supabase_adapter.py](services/supabase_adapter.py)
- [app.py](app.py)

**Ações**

1. Adotar na view a operação de domínio `data_service.delete_mes(...)`, que já existe na camada de serviço.
2. Exigir confirmação forte para exclusão.
3. Remover renderização insegura de texto livre no bloco de conciliação do `Raio-X`.
4. Corrigir a semântica de ciclo aberto vs fechado:
   `Aporte Projetado`/`Aporte Real`,
   `Savings Rate Atual`/`Savings Rate Final`.
5. Cachear `_get_git_info()` em `app.py`.
6. Aproveitar a etapa para quick wins sem risco de comportamento:
   remover `import PIL.Image` duplicado em `tab_settings.py`,
   alinhar o tipo de retorno real de `render_onboarding()`.

**Critério de aceite**

1. Exclusão usa a operação de domínio já existente.
2. UI não chama de "real" um valor de ciclo aberto.
3. Não há regressão funcional em importação, histórico e exclusão.

---

## Etapa 2 — Fundação visual mobile-first

**Objetivo**

Criar a nova base visual em duas fatias, para reduzir risco e evitar uma reescrita monolítica de `styles.py`.

**Gate obrigatório antes de seguir**

Nenhuma tela pode avançar para migração estrutural enquanto a Etapa 2 não estiver validada em mobile real ou viewport equivalente (`393x852`) com:

1. tabs legíveis;
2. tipografia estável;
3. contrastes corretos;
4. sem truncamento crítico;
5. sem regressão funcional induzida por CSS.

**Arquivo principal**

- [views/styles.py](views/styles.py)

### Subetapa 2a — Tokens, tipografia e arquitetura responsiva

**Ações**

1. Trocar a arquitetura atual baseada em `@media (max-width: ...)` por uma base-mobile com `@media (min-width: ...)`.
2. Introduzir tokens semânticos de cor, tipografia, spacing, radius e shadow.
3. Substituir `Inter` por `Manrope Variable`.
4. Aplicar `tabular-nums` a métricas, badges numéricos, tabelas e resumos.
5. Reduzir gradientes fortes, brilhos e contrastes dramáticos sem alterar ainda a estrutura das views.

**Critério de aceite**

1. O app continua funcional.
2. A base visual já fica mais limpa.
3. Não há regressão de legibilidade em mobile.

### Subetapa 2b — Primitives novas e camada de compatibilidade

**Ações**

1. Criar primitives reutilizáveis:
   `.page-header`,
   `.context-bar`,
   `.hero-card`,
   `.kpi-card`,
   `.section-block`,
   `.data-card`,
   `.status-pill`,
   `.danger-zone`,
   `.action-callout`.
2. Manter, por compatibilidade, as classes antigas durante a migração das views.
3. Evitar colisão de seletores amplos; preferir classes próprias às sobrescritas genéricas quando possível.

**Critério de aceite**

1. As novas primitives coexistem com o legado sem quebrar as telas atuais.
2. A migração das views pode acontecer de forma progressiva.

---

## Etapa 3 — Shell de navegação e estrutura global

**Objetivo**

Ajustar a moldura do produto para mobile-first antes da migração das páginas internas.

**Arquivos**

- [app.py](app.py)
- [views/styles.py](views/styles.py)

**Ações**

1. Revisar o header global para reduzir ruído visual.
2. Encurtar os rótulos das tabs se necessário para uso real em mobile.
   Recomendação:
   `🔬 Raio-X`, `📈 Histórico`, `🤖 IA`, `⚙️ Config`.
3. Ajustar o espaçamento vertical global entre tabs, seções e rodapé.
4. Reduzir duplicação visual entre sidebar e footer.
5. Garantir que a navegação principal seja legível e tocável em `393px`.

**Critério de aceite**

1. Tabs cabem e permanecem legíveis em mobile.
2. O shell da aplicação deixa de ser o ponto de estrangulamento visual.

---

## Etapa 4 — Rebuild do `Raio-X do Ciclo`

**Objetivo**

Transformar o `Raio-X` na tela de decisão principal do produto.

**Gate obrigatório antes de seguir**

Não avançar do `Raio-X` para as demais telas enquanto esta etapa não estiver aprovada em mobile-first.

Checklist mínimo de aprovação em `393x852`:

1. contexto-base visível sem esforço;
2. hero legível sem truncamento;
3. fila de ações útil e não redundante;
4. KPIs compreensíveis em coluna única;
5. conciliação e resumo respondendo perguntas diferentes;
6. sem scroll lateral inesperado nos blocos principais.

**Arquivo principal**

- [views/tab_raiox.py](views/tab_raiox.py)

**Subetapa 4.1 — Estrutura do topo**

**Ações**

1. Adicionar logo abaixo do seletor do ciclo uma `context-bar` com:
   Receita Base, Teto, Meta de Aporte, Fechamento.
2. Reestruturar o topo em ordem:
   contexto do ciclo,
   hero card,
   fila de ações,
   KPIs secundários.

**Critério de aceite**

O usuário entende o contexto-base do mês sem rolar.

### Subetapa 4.2 — Hero e fila de ações

**Ações**

1. Substituir o card atual de sobrevivência por um `hero-card` mais sóbrio.
2. O hero deve responder:
   quanto ainda pode gastar por dia,
   até quando,
   e qual o status do ciclo.
3. Abaixo do hero, criar uma fila curta de ações priorizadas:
   conciliação pendente,
   categoria acima do esperado,
   risco de meta,
   não classificados.
4. Limitar a no máximo 3 ações visíveis antes de agrupamento.
5. Remover do hero qualquer texto que reapareça integralmente nos alertas logo abaixo.

**Critério de aceite**

O topo da tela passa a dizer o que o usuário precisa fazer, não só o que aconteceu.

### Subetapa 4.3 — KPIs e semântica de leitura

**Ações**

1. Reorganizar os KPIs em prioridade:
   saldo para variáveis,
   aporte projetado/final,
   savings rate atual/final,
   risco do teto.
2. Manter `Envelope inicial` como apoio secundário, não dentro do valor principal do KPI.
3. Padronizar a linguagem dos deltas:
   `vs. ciclo anterior`,
   `pp` para percentuais,
   sem abreviações ambíguas.
4. Não repetir no KPI uma mensagem já expressa por badge, callout e resumo ao mesmo tempo.

**Critério de aceite**

Os números principais ficam escaneáveis em mobile sem perda de contexto.

### Subetapa 4.4 — Conciliação, resumo e composição

**Ações**

1. Manter `Conciliação` como bloco explícito para responder à pergunta:
   `o que ainda precisa ser conferido?`
2. Fazer o bloco de `Conciliação` mostrar progresso e pendências, com prioridade visual para itens pendentes.
3. Fazer o bloco `💳 Cartão` do resumo responder outra pergunta:
   `qual é o total financeiro dos fixos de cartão neste ciclo?`
4. No resumo de `💳 Cartão`, remover a listagem completa com `Descrição + Valor + Status`; manter apenas total, contagem e resumo curto de conciliação.
5. Enxugar o `Resumo do Orçamento`, mantendo só o que complementa os cards.
6. Reestilizar expanders e dataframes com densidade de tabela financeira.
7. Garantir que nenhum item financeiro relevante apareça simultaneamente como:
   card principal,
   linha de resumo,
   badge,
   e alerta textual.

**Critério de aceite**

O usuário não vê duas representações quase idênticas do mesmo conjunto de dados.

### Subetapa 4.5 — Gráficos e tabela de lançamentos

**Ações**

1. Manter a base analítica atual, sem trocar fonte de dados.
2. Reduzir ruído cromático nos gráficos.
3. Usar a cor de dado principal com mais destaque e eixos/grid mais discretos.
4. Evitar excesso de anotações simultâneas.
5. Garantir que a tabela de lançamentos em mobile mantenha busca, filtro e leitura horizontal controlada.

**Critério de aceite**

Os gráficos explicam, mas não competem com os blocos de decisão.

---

## Etapa 5 — Rebuild do `Evolução Histórica`

**Objetivo**

Dar ao histórico um papel de análise, não de ruído visual.

**Arquivo principal**

- [views/tab_historico.py](views/tab_historico.py)

**Ações**

1. Corrigir o contraste da linha `Total` no gráfico empilhado.
2. Reestilizar títulos, badges e tabelas para a nova linguagem visual.
3. Reduzir o peso visual de elementos decorativos.
4. Manter destaque claro para:
   melhor mês,
   pior mês,
   previsão,
   sazonalidade.
5. Garantir que tabelas históricas permaneçam auditáveis em mobile com scroll controlado.
6. Não alterar fórmulas nesta etapa; só semântica, ordem, densidade e visualização.
7. Validar que cada gráfico responde uma pergunta distinta antes de mantê-lo na tela.

**Critério de aceite**

O histórico fica mais legível em mobile e desktop sem perder profundidade analítica.

---

## Etapa 6 — Rebuild de `Configurações`, `IA` e `Onboarding`

**Objetivo**

Melhorar completude operacional sem transformar essas telas em formulários intermináveis.

**Arquivos**

- [views/tab_settings.py](views/tab_settings.py)
- [views/tab_importacao.py](views/tab_importacao.py)
- [views/onboarding.py](views/onboarding.py)

### Subetapa 6.1 — Configurações

**Ações**

1. Agrupar a página em blocos visuais:
   importação,
   editor manual,
   gastos fixos,
   novo mês,
   exclusão,
   parâmetros,
   limites por categoria,
   metas.
2. Dar tratamento visual de `danger-zone` ao bloco de exclusão.
3. Melhorar a leitura dos blocos longos em mobile com spacing e cards.
4. Manter o fluxo funcional atual; reorganizar primeiro, refatorar módulo só depois, se necessário.

### Subetapa 6.2 — Importação e IA

**Ações**

1. Dar mais destaque ao estado do processo:
   upload,
   leitura,
   preview,
   classificação,
   confirmação.
2. Tornar o preview e os ignorados mais claros em mobile.
3. Preservar as regras atuais de classificação; mexer no fluxo visual, não na inferência.

### Subetapa 6.3 — Onboarding

**Ações**

1. Ajustar a tipagem de retorno de `render_onboarding()`.
2. Reorganizar cada passo para caber confortavelmente em mobile sem parecer comprimido.
3. Garantir um passo por foco principal, sem excesso de elementos concorrentes.

**Critério de aceite**

O usuário consegue operar importação, edição, criação e exclusão de ciclo em mobile sem fadiga visual desnecessária.

---

## Etapa 7 — Acessibilidade, consistência e limpeza

**Objetivo**

Fechar a migração removendo inconsistências remanescentes.

**Arquivos**

- [views/styles.py](views/styles.py)
- [views/tab_raiox.py](views/tab_raiox.py)
- [views/tab_historico.py](views/tab_historico.py)
- [views/onboarding.py](views/onboarding.py)

**Ações**

1. Remover imports inline e recomputações óbvias em `tab_raiox.py`.
2. Revisar contraste AA para textos menores que `24px`.
3. Revisar foco visível, estados de hover/pressed, badges e alerts.
4. Reduzir animações a interações realmente úteis.
5. Remover classes legadas de CSS que não estiverem mais em uso.

**Critério de aceite**

O código e a UI convergem para uma base mais simples, coerente e sustentável.

---

## Etapa 8 — Verificação final e rollback-safe

**Objetivo**

Encerrar a implementação com confiança de comportamento e layout.

**Ações**

1. Executar testes automatizados relevantes.
2. Validar manualmente cada tela em `393px`, `768px` e `1440px`.
3. Comparar com a baseline da Etapa 0.
4. Verificar regressões de:
   deduplicação,
   exclusão,
   filtros,
   gráficos,
   dataframes,
   onboarding.
5. Confirmar que nenhum componente crítico depende de correção posterior em mobile.

**Critério de aceite**

O produto pode ser considerado migrado sem "segunda rodada obrigatória" de correção responsiva.

---

## Ordem recomendada de PRs ou fatias de entrega

1. PR 1:
   Hotfix H1 + Etapa 1.
2. PR 2:
   Etapa 2a + Etapa 3.
3. PR 3:
   Etapa 2b.
4. PR 4:
   Etapa 4.
5. PR 5:
   Etapa 5.
6. PR 6:
   Etapa 6.
7. PR 7:
   Etapas 7 e 8.

Essa ordem minimiza risco porque:

1. corrige comportamento antes de alterar forma;
2. estabelece a fundação visual antes da migração das páginas;
3. ataca o `Raio-X` primeiro, que é a principal superfície de valor do produto.

---

## Arquivos com maior impacto nesta rodada

| Arquivo | Papel na implementação |
|---|---|
| [views/styles.py](views/styles.py) | nova fundação visual e responsiva |
| [views/tab_raiox.py](views/tab_raiox.py) | principal redesign funcional e visual |
| [views/tab_historico.py](views/tab_historico.py) | consolidação analítica e responsiva |
| [views/tab_settings.py](views/tab_settings.py) | hardening de exclusão e UX operacional |
| [views/tab_importacao.py](views/tab_importacao.py) | fluxo de IA/importação mais claro |
| [views/onboarding.py](views/onboarding.py) | onboarding enxuto em mobile |
| [services/data_engine.py](services/data_engine.py) | regra canônica de dedup e semântica financeira |
| [services/supabase_adapter.py](services/supabase_adapter.py) | exclusão por domínio |
| [tests/test_data_engine.py](tests/test_data_engine.py) | cobertura de não regressão |
| [app.py](app.py) | shell, tabs e metadata global |

---

## Plano de verificação

### Testes automatizados

Executar no ambiente virtual do projeto:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/test_data_engine.py tests/test_new_features.py -v
```

Se houver ambiente com Streamlit testável, adicionar smoke tests de render das telas principais.

### Matriz manual por viewport

#### 393px

1. tabs legíveis;
2. hero do `Raio-X` sem truncamento;
3. KPIs empilhados corretamente;
4. tabelas com scroll controlado;
5. exclusão de mês utilizável;
6. onboarding confortável.
7. nenhuma mesma informação aparecendo em hero + KPI + alerta com o mesmo texto.

#### 768px

1. distribuição de duas colunas consistente;
2. gráficos sem colisão de labels;
3. cards sem espaços mortos exagerados.

#### 1440px

1. densidade visual adequada;
2. KPIs em quatro colunas;
3. histórico e resumo com leitura fluida;
4. ausência de áreas excessivamente vazias.
5. ausência de repetição visual mascarada por espaço sobrando.

### Fluxos manuais obrigatórios

1. Abrir histórico com 6+ meses e validar sazonalidade.
2. Editar lançamentos manualmente e salvar.
3. Excluir mês e validar confirmação forte.
4. Navegar entre os quatro tabs em mobile.
5. Inserir descrição com HTML e verificar renderização segura.
6. Validar um ciclo aberto e um ciclo fechado para semântica de `Aporte` e `Savings Rate`.
7. Revisar cada tela perguntando:
   qual é a informação principal,
   onde ela aparece,
   e se ela está sendo repetida em outro bloco sem ganho real.

---

## Itens fora do escopo desta rodada

| Item | Motivo |
|---|---|
| Unificação da regra de dedup OCR | Fora do escopo deste ciclo. A regra atual está estável em uso e qualquer unificação agora pode alterar comportamento em produção. |
| Cache amplo de leituras do Supabase | exige política coordenada de invalidação |
| Split completo de `views/tab_settings.py` em múltiplos módulos | desejável, mas não obrigatório para esta rodada |
| Reescrita total dos gráficos para novas bibliotecas/componentes | risco alto sem ganho imediato equivalente |
| Novas features financeiras grandes | precisam de discovery e testes próprios |
| Segunda família tipográfica decorativa | adiciona complexidade sem ganho direto em dashboard financeiro |

---

## Definição final de pronto

Esta rodada só estará concluída quando:

1. os riscos de integridade e exclusão estiverem corrigidos;
2. a UI tiver a nova fundação visual aplicada;
3. `Raio-X`, histórico, configurações, IA e onboarding funcionarem em mobile sem remendos posteriores;
4. os números principais forem semanticamente corretos;
5. a experiência parecer mais clara, mais premium e mais objetiva sem sacrificar confiança operacional.
