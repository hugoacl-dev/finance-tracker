-- ═══════════════════════════════════════
-- FTracker: Migração — Goals + Category Budgets
-- Execute no Supabase SQL Editor
-- ═══════════════════════════════════════

-- 1. Metas de Longo Prazo
CREATE TABLE IF NOT EXISTS goals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    titulo TEXT NOT NULL,
    valor_alvo NUMERIC NOT NULL,
    prazo_meses INT NOT NULL DEFAULT 12,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Orçamento por Categoria
CREATE TABLE IF NOT EXISTS category_budgets (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    categoria TEXT NOT NULL,
    limite NUMERIC NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (profile_id, categoria)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_goals_profile ON goals(profile_id);
CREATE INDEX IF NOT EXISTS idx_cat_budgets_profile ON category_budgets(profile_id);

-- RLS (Row Level Security) — se estiver ativo no Supabase
ALTER TABLE goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_budgets ENABLE ROW LEVEL SECURITY;

-- Políticas permissivas (ajustar se usar auth real)
CREATE POLICY "Allow all for goals" ON goals FOR ALL USING (true);
CREATE POLICY "Allow all for category_budgets" ON category_budgets FOR ALL USING (true);
