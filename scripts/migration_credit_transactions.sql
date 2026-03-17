-- Migration: suporte a transações de crédito na fatura
-- Execute no Supabase SQL Editor

ALTER TABLE transacoes
  ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'debito'
  CHECK (tipo IN ('debito', 'credito'));
