-- ─── CLIENTES ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id          BIGSERIAL PRIMARY KEY,
    phone       TEXT UNIQUE NOT NULL,
    name        TEXT DEFAULT '',
    source      TEXT DEFAULT '',        -- instagram | facebook | google | whatsapp
    status      TEXT DEFAULT 'novo',   -- novo | orcamento | pedido | concluido | perdido
    notes       TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── MENSAGENS ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,
    phone       TEXT NOT NULL,
    role        TEXT NOT NULL,          -- user | assistant
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── PEDIDOS / ORÇAMENTOS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id              BIGSERIAL PRIMARY KEY,
    phone           TEXT NOT NULL,
    produto         TEXT DEFAULT 'Patch 3D',
    quantidade      TEXT DEFAULT '',
    tamanho         TEXT DEFAULT '',
    tem_estrelas    BOOLEAN DEFAULT FALSE,
    valor_estimado  NUMERIC(10,2) DEFAULT 0,
    valor_entrada   NUMERIC(10,2) DEFAULT 0,
    status          TEXT DEFAULT 'orcamento',  -- orcamento | confirmado | producao | pronto | entregue
    arte_status     TEXT DEFAULT 'aguardando', -- aguardando | recebida | aprovada
    obs             TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── ÍNDICES ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(phone);
CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
