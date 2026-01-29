PLAN_LEVELS = {'free': 0, 'starter': 1, 'pro': 2, 'agency': 3}

# ✅ cole aqui seu AGENTS_CONFIG inteiro (o mesmo que você já tem)
AGENTS_CONFIG = {
    # --- PLANO AGENCY ---
    'instavideo': {
        'name': 'Gerador de Reels Viral',
        'icon': '🎬',
        'type': 'video',
        'prompt': 'Crie um roteiro de vídeo curto, dinâmico e com ganchos virais para Instagram/TikTok.',
        'min_plan': 'agency',
        'example_input': 'Promoção de Queima de Estoque de Inverno: Todas as jaquetas com 50% OFF, apenas neste fim de semana.'
    },

    # --- PLANO PRO ---
    'scanner': {
        'name': 'Scanner de Preços (Foto)',
        'icon': '📸',
        'type': 'scanner_price',
        'prompt': 'Analise a foto, identifique o produto exato e busque preços online.',
        'min_plan': 'pro',
        'example_input': '(Envie a foto do produto) Identifique este vinho e me diga se o preço que estou pagando (R$ 80,00) está justo.'
    },
    'price': {
        'name': 'Caçador de Preços (Busca)',
        'icon': '💰',
        'type': 'shopping',
        'prompt': 'Faça um ranking de preços online para este produto no mercado brasileiro.',
        'min_plan': 'pro',
        'example_input': 'iPhone 15 Pro Max 256GB Titânio Natural'
    },
    'stock': {
        'name': 'Gestor de Estoque (Foto)',
        'icon': '📦',
        'type': 'image',
        'prompt': 'Analise a foto da prateleira, estime a quantidade de itens e sugira reposição baseada em organização visual.',
        'min_plan': 'pro',
        'example_input': '(Envie a foto da prateleira) Conte quantas latas de refrigerante existem e se parecem organizadas.'
    },
    'spy': {
        'name': 'Espião de Concorrente',
        'icon': '🕵️',
        'type': 'url_input',
        'prompt': 'Analise o link do concorrente, identifique pontos fortes, fracos e oportunidades para superá-lo.',
        'min_plan': 'pro',
        'example_input': 'https://www.instagram.com/loja_concorrente_exemplo'
    },
    'audit': {
        'name': 'Auditoria Operacional',
        'icon': '🏠',
        'type': 'url_self',
        'prompt': 'Analise meus reviews recentes no Google Maps e sugira melhorias operacionais urgentes.',
        'min_plan': 'pro',
        'example_input': 'https://www.google.com/maps/place/minha_loja'
    },

    # --- PLANO STARTER ---
    'instapost': {
        'name': 'Criador de Post Insta',
        'icon': '📸',
        'type': 'text',
        'prompt': 'Crie uma legenda engajadora, sugestão visual de foto e 10 hashtags estratégicas.',
        'min_plan': 'starter',
        'example_input': 'Post para o Dia dos Namorados focando em jantar romântico à luz de velas na nossa pizzaria.'
    },
    'review_reply': {
        'name': 'Resposta de Review',
        'icon': '💬',
        'type': 'text',
        'prompt': 'Escreva uma resposta profissional, empática e orientada à resolução para este review de cliente.',
        'min_plan': 'starter',
        'example_input': 'Cliente reclamou que a entrega atrasou 40 minutos e a comida chegou fria. Nome dele é Carlos.'
    },
    'promo': {
        'name': 'Campanhas Promocionais',
        'icon': '📣',
        'type': 'text',
        'prompt': 'Crie 3 ideias de campanhas criativas e de baixo custo para atrair clientes.',
        'min_plan': 'starter',
        'example_input': 'Loja de roupas femininas querendo liquidar a coleção de verão para abrir espaço para o outono.'
    },
    'persona': {
        'name': 'Definidor de Persona',
        'icon': '👥',
        'type': 'text',
        'prompt': 'Defina a persona detalhada do cliente ideal (ICP), incluindo dores, desejos e hábitos de consumo.',
        'min_plan': 'starter',
        'example_input': 'Hamburgueria artesanal gourmet localizada em bairro universitário, preço médio R$ 45,00.'
    },
    'menu_eng': {
        'name': 'Engenharia de Menu',
        'icon': '🍔',
        'type': 'text',
        'prompt': 'Analise os itens descritos e sugira otimizações para aumentar o lucro (destaque os Cash Cows).',
        'min_plan': 'starter',
        'example_input': 'Meu prato mais vendido é o Parmegiana (mas o lucro é baixo) e o que tem maior margem é o Risoto (mas vende pouco). O que fazer?'
    },
    'sop': {
        'name': 'Gerador de POP',
        'icon': '📝',
        'type': 'text',
        'prompt': 'Crie um Procedimento Operacional Padrão (POP) detalhado, passo a passo, para a tarefa solicitada.',
        'min_plan': 'starter',
        'example_input': 'Rotina de abertura de caixa e limpeza do balcão para os atendentes da manhã.'
    },
    'job_desc': {
        'name': 'Descrição de Vaga',
        'icon': '👔',
        'type': 'text',
        'prompt': 'Crie uma descrição de vaga atraente, listando responsabilidades, requisitos e benefícios.',
        'min_plan': 'starter',
        'example_input': 'Vendedor sênior para loja de calçados em shopping, necessário experiência com metas agressivas.'
    },
    'interview': {
        'name': 'Perguntas de Entrevista',
        'icon': '🎤',
        'type': 'text',
        'prompt': 'Liste 10 perguntas técnicas e comportamentais para entrevistar um candidato a esta vaga.',
        'min_plan': 'starter',
        'example_input': 'Candidato para vaga de Gerente de Loja em uma franquia de chocolates.'
    },
    'contract': {
        'name': 'Revisor de Contrato',
        'icon': '⚖️',
        'type': 'text',
        'prompt': 'Analise este texto jurídico/contratual em busca de cláusulas abusivas ou riscos para o contratante.',
        'min_plan': 'starter',
        'example_input': 'Cole aqui a cláusula de fidelidade do contrato com o fornecedor de internet que você quer analisar.'
    },
    'supplier': {
        'name': 'Negociador de Fornecedor',
        'icon': '🤝',
        'type': 'text',
        'prompt': 'Escreva um e-mail formal e persuasivo para negociar preços ou prazos com um fornecedor.',
        'min_plan': 'starter',
        'example_input': 'O fornecedor de embalagens aumentou o preço em 15% sem aviso prévio. Escreva um e-mail pedindo a manutenção do preço antigo.'
    },
    'localseo': {
        'name': 'SEO Local (GMB)',
        'icon': '📍',
        'type': 'text',
        'prompt': 'Crie uma descrição otimizada para o Perfil da Empresa no Google (GMB) usando palavras-chave locais.',
        'min_plan': 'starter',
        'example_input': 'Barbearia clássica no centro de Curitiba, oferecemos cerveja artesanal e toalha quente.'
    },
    'upsell': {
        'name': 'Técnicas de Upsell',
        'icon': '📈',
        'type': 'text',
        'prompt': 'Sugira um script de vendas para aumentar o ticket médio (Upsell ou Cross-sell) no momento da compra.',
        'min_plan': 'starter',
        'example_input': 'O cliente acabou de comprar um terno completo. O que o vendedor deve oferecer para complementar a venda?'
    },
    'crisis': {
        'name': 'Gestão de Crise',
        'icon': '🚨',
        'type': 'text',
        'prompt': 'Crie um plano de comunicação e nota oficial para conter danos de uma crise de reputação.',
        'min_plan': 'starter',
        'example_input': 'Um cliente encontrou um cabelo na comida, postou no Instagram e o vídeo viralizou na cidade.'
    },
    'waste': {
        'name': 'Anti-Desperdício',
        'icon': '🗑️',
        'type': 'text',
        'prompt': 'Sugira receitas criativas ou processos para reaproveitar sobras e evitar desperdício de insumos.',
        'min_plan': 'starter',
        'example_input': 'Tenho muita sobra de arroz cozido e tomates maduros no restaurante todos os dias. O que fazer?'
    },
    'event': {
        'name': 'Planejador de Eventos',
        'icon': '🎉',
        'type': 'text',
        'prompt': 'Crie um cronograma completo e checklist para organizar um evento na loja.',
        'min_plan': 'starter',
        'example_input': 'Inauguração da nova filial da loja de cosméticos com coquetel para 50 pessoas.'
    },
    'delivery': {
        'name': 'Otimizador de Delivery',
        'icon': '🛵',
        'type': 'text',
        'prompt': 'Sugira melhorias para embalagem, logística e experiência do cliente no delivery.',
        'min_plan': 'starter',
        'example_input': 'Os lanches estão chegando revirados e frios na casa do cliente por causa da trepidação da moto.'
    }
}
