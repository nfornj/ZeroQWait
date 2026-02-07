-- Enable RLS on tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE shops ENABLE ROW LEVEL SECURITY;
ALTER TABLE queues ENABLE ROW LEVEL SECURITY;
ALTER TABLE queue_items ENABLE ROW LEVEL SECURITY;

-- Note: App must set `app.current_user_id` config parameter for these to work.

-- USERS Table
-- Users can read/write their own data
CREATE POLICY user_isolation_policy ON users
    FOR ALL
    USING (id = current_setting('app.current_user_id', true)::int);

-- SHOPS Table
-- Public read
CREATE POLICY shop_public_read_policy ON shops
    FOR SELECT
    USING (true);

-- Owners can modify their own shops
CREATE POLICY shop_owner_policy ON shops
    FOR ALL
    USING (owner_id = current_setting('app.current_user_id', true)::int)
    WITH CHECK (owner_id = current_setting('app.current_user_id', true)::int);

-- QUEUES Table
-- Public read (for joining)
CREATE POLICY queue_public_read_policy ON queues
    FOR SELECT
    USING (true);

-- Shop owners can modify queues for their shops
CREATE POLICY queue_owner_policy ON queues
    FOR ALL
    USING (shop_id IN (
        SELECT id FROM shops WHERE owner_id = current_setting('app.current_user_id', true)::int
    ));

-- QUEUE ITEMS Table
-- Users can see their own items
CREATE POLICY queue_item_user_read_policy ON queue_items
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::int);

-- Shop owners can see all items in their queues
CREATE POLICY queue_item_shop_read_policy ON queue_items
    FOR SELECT
    USING (queue_id IN (
        SELECT q.id FROM queues q
        JOIN shops s ON q.shop_id = s.id
        WHERE s.owner_id = current_setting('app.current_user_id', true)::int
    ));
