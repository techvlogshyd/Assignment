-- seed data for order processing app
-- passwords: password123 (bcrypt)

insert into users (id, email, hashed_password, role, created_at) values
  ('a0000000-0000-0000-0000-000000000001', 'admin@example.com',  '$2b$12$JhRSrsZCBry.MA4N8NiIJ.P.DHu54lW1PGmfSBsVnUvMQHjC7Q9eO', 'admin',  now() - interval '30 days'),
  ('a0000000-0000-0000-0000-000000000002', 'editor@example.com', '$2b$12$O2s8yrlPA.OtdV.VLZGjT.qUSgokxUpRzuUkmUzQwzfrKCccp1Wf.', 'editor', now() - interval '30 days'),
  ('a0000000-0000-0000-0000-000000000003', 'viewer@example.com', '$2b$12$CjMEhd0fNQLJ94GV1fK1sO252gL.tAFazBMmsEsW7T6dzupXvqkUy', 'viewer', now() - interval '30 days')
on conflict (email) do nothing;

-- 47 orders across all statuses, spread over last 30 days
-- external_id EXT-001, EXT-002, EXT-003 match orders_upload.csv (triggers B2 idempotency bug)
-- amounts chosen to expose float precision drift when summed (0.1 * 3 = 0.30000000000000004 in Python float)

insert into orders (id, external_id, customer_name, items, total_amount, status, created_at, updated_at) values
  -- pending orders (12)
  ('b0000000-0000-0000-0000-000000000001', 'EXT-001', 'Alice Smith',   '[{"name": "Widget A", "price": 0.1, "quantity": 3}]',                                  0.3,     'pending',    now() - interval '0 days',  now() - interval '0 days'),
  ('b0000000-0000-0000-0000-000000000002', 'EXT-002', 'Bob Jones',     '[{"name": "Gadget B", "price": 0.2, "quantity": 2}]',                                  0.4,     'pending',    now() - interval '1 days',  now() - interval '1 days'),
  ('b0000000-0000-0000-0000-000000000003', 'EXT-003', 'Carol White',   '[{"name": "Doohickey C", "price": 0.7, "quantity": 1}]',                               0.7,     'pending',    now() - interval '2 days',  now() - interval '2 days'),
  ('b0000000-0000-0000-0000-000000000004', 'EXT-101', 'Dave Brown',    '[{"name": "Thingamajig D", "price": 9.99, "quantity": 5}]',                            49.95,   'pending',    now() - interval '3 days',  now() - interval '3 days'),
  ('b0000000-0000-0000-0000-000000000005', 'EXT-102', 'Eve Davis',     '[{"name": "Whatchamacallit E", "price": 14.5, "quantity": 2}]',                        29.0,    'pending',    now() - interval '4 days',  now() - interval '4 days'),
  ('b0000000-0000-0000-0000-000000000006', 'EXT-103', 'Frank Miller',  '[{"name": "Gizmo F", "price": 3.25, "quantity": 10}]',                                 32.5,    'pending',    now() - interval '5 days',  now() - interval '5 days'),
  ('b0000000-0000-0000-0000-000000000007', 'EXT-104', 'Grace Wilson',  '[{"name": "Contraption G", "price": 0.1, "quantity": 7}]',                             0.7,     'pending',    now() - interval '6 days',  now() - interval '6 days'),
  ('b0000000-0000-0000-0000-000000000008', 'EXT-105', 'Hank Moore',    '[{"name": "Apparatus H", "price": 19.99, "quantity": 1}]',                             19.99,   'pending',    now() - interval '7 days',  now() - interval '7 days'),
  ('b0000000-0000-0000-0000-000000000009', 'EXT-106', 'Ida Taylor',    '[{"name": "Mechanism I", "price": 0.2, "quantity": 5}]',                               1.0,     'pending',    now() - interval '8 days',  now() - interval '8 days'),
  ('b0000000-0000-0000-0000-00000000000a', 'EXT-107', 'Jack Anderson', '[{"name": "Device J", "price": 7.77, "quantity": 3}]',                                 23.31,   'pending',    now() - interval '9 days',  now() - interval '9 days'),
  ('b0000000-0000-0000-0000-00000000000b', 'EXT-108', 'Karen Thomas',  '[{"name": "Contraption K", "price": 0.1, "quantity": 2}, {"name": "Widget L", "price": 0.2, "quantity": 1}]', 0.4, 'pending', now() - interval '10 days', now() - interval '10 days'),
  ('b0000000-0000-0000-0000-00000000000c', 'EXT-109', 'Leo Jackson',   '[{"name": "Gadget M", "price": 55.0, "quantity": 1}]',                                 55.0,    'pending',    now() - interval '11 days', now() - interval '11 days'),

  -- processing orders (10)
  ('b0000000-0000-0000-0000-00000000000d', 'EXT-201', 'Mary Harris',   '[{"name": "Unit N", "price": 12.5, "quantity": 4}]',                                   50.0,    'processing', now() - interval '12 days', now() - interval '11 days'),
  ('b0000000-0000-0000-0000-00000000000e', 'EXT-202', 'Ned Martin',    '[{"name": "Part O", "price": 0.7, "quantity": 3}]',                                    2.1,     'processing', now() - interval '13 days', now() - interval '12 days'),
  ('b0000000-0000-0000-0000-00000000000f', 'EXT-203', 'Olive Garcia',  '[{"name": "Component P", "price": 99.0, "quantity": 2}]',                              198.0,   'processing', now() - interval '14 days', now() - interval '13 days'),
  ('b0000000-0000-0000-0000-000000000010', 'EXT-204', 'Paul Martinez', '[{"name": "Element Q", "price": 0.1, "quantity": 10}]',                                1.0,     'processing', now() - interval '15 days', now() - interval '14 days'),
  ('b0000000-0000-0000-0000-000000000011', 'EXT-205', 'Quinn Robinson','[{"name": "Module R", "price": 34.99, "quantity": 3}]',                                104.97,  'processing', now() - interval '16 days', now() - interval '15 days'),
  ('b0000000-0000-0000-0000-000000000012', 'EXT-206', 'Rose Clark',    '[{"name": "Assembly S", "price": 0.2, "quantity": 7}]',                                1.4,     'processing', now() - interval '17 days', now() - interval '16 days'),
  ('b0000000-0000-0000-0000-000000000013', 'EXT-207', 'Sam Lewis',     '[{"name": "System T", "price": 149.99, "quantity": 1}]',                               149.99,  'processing', now() - interval '18 days', now() - interval '17 days'),
  ('b0000000-0000-0000-0000-000000000014', 'EXT-208', 'Tina Lee',      '[{"name": "Package U", "price": 8.5, "quantity": 6}]',                                 51.0,    'processing', now() - interval '19 days', now() - interval '18 days'),
  ('b0000000-0000-0000-0000-000000000015', 'EXT-209', 'Uma Walker',    '[{"name": "Bundle V", "price": 0.1, "quantity": 1}, {"name": "Bundle W", "price": 0.2, "quantity": 1}]', 0.3, 'processing', now() - interval '20 days', now() - interval '19 days'),
  ('b0000000-0000-0000-0000-000000000016', 'EXT-210', 'Vic Hall',      '[{"name": "Set X", "price": 24.0, "quantity": 5}]',                                    120.0,   'processing', now() - interval '21 days', now() - interval '20 days'),

  -- completed orders (18)
  ('b0000000-0000-0000-0000-000000000017', 'EXT-301', 'Wendy Allen',   '[{"name": "Item Y", "price": 5.0, "quantity": 2}]',                                    10.0,    'completed',  now() - interval '22 days', now() - interval '21 days'),
  ('b0000000-0000-0000-0000-000000000018', 'EXT-302', 'Xander Young',  '[{"name": "Item Z", "price": 0.1, "quantity": 3}]',                                    0.3,     'completed',  now() - interval '22 days', now() - interval '21 days'),
  ('b0000000-0000-0000-0000-000000000019', 'EXT-303', 'Yara Hernandez','[{"name": "Product AA", "price": 75.0, "quantity": 2}]',                               150.0,   'completed',  now() - interval '23 days', now() - interval '22 days'),
  ('b0000000-0000-0000-0000-00000000001a', 'EXT-304', 'Zoe King',      '[{"name": "Product BB", "price": 0.2, "quantity": 4}]',                                0.8,     'completed',  now() - interval '23 days', now() - interval '22 days'),
  ('b0000000-0000-0000-0000-00000000001b', 'EXT-305', 'Aaron Wright',  '[{"name": "Product CC", "price": 18.99, "quantity": 5}]',                              94.95,   'completed',  now() - interval '24 days', now() - interval '23 days'),
  ('b0000000-0000-0000-0000-00000000001c', 'EXT-306', 'Beth Lopez',    '[{"name": "Product DD", "price": 0.7, "quantity": 2}]',                                1.4,     'completed',  now() - interval '24 days', now() - interval '23 days'),
  ('b0000000-0000-0000-0000-00000000001d', 'EXT-307', 'Carl Hill',     '[{"name": "Product EE", "price": 250.0, "quantity": 1}]',                              250.0,   'completed',  now() - interval '25 days', now() - interval '24 days'),
  ('b0000000-0000-0000-0000-00000000001e', 'EXT-308', 'Diana Scott',   '[{"name": "Product FF", "price": 0.1, "quantity": 5}]',                                0.5,     'completed',  now() - interval '25 days', now() - interval '24 days'),
  ('b0000000-0000-0000-0000-00000000001f', 'EXT-309', 'Eli Green',     '[{"name": "Product GG", "price": 42.0, "quantity": 3}]',                               126.0,   'completed',  now() - interval '25 days', now() - interval '25 days'),
  ('b0000000-0000-0000-0000-000000000020', 'EXT-310', 'Fiona Adams',   '[{"name": "Product HH", "price": 0.2, "quantity": 3}]',                                0.6,     'completed',  now() - interval '26 days', now() - interval '25 days'),
  ('b0000000-0000-0000-0000-000000000021', 'EXT-311', 'George Baker',  '[{"name": "Product II", "price": 7.5, "quantity": 8}]',                                60.0,    'completed',  now() - interval '26 days', now() - interval '26 days'),
  ('b0000000-0000-0000-0000-000000000022', 'EXT-312', 'Hannah Carter', '[{"name": "Product JJ", "price": 0.1, "quantity": 4}]',                                0.4,     'completed',  now() - interval '27 days', now() - interval '26 days'),
  ('b0000000-0000-0000-0000-000000000023', 'EXT-313', 'Ivan Davis',    '[{"name": "Product KK", "price": 33.33, "quantity": 3}]',                              99.99,   'completed',  now() - interval '27 days', now() - interval '27 days'),
  ('b0000000-0000-0000-0000-000000000024', 'EXT-314', 'Julia Evans',   '[{"name": "Product LL", "price": 0.2, "quantity": 2}]',                                0.4,     'completed',  now() - interval '27 days', now() - interval '27 days'),
  ('b0000000-0000-0000-0000-000000000025', 'EXT-315', 'Karl Foster',   '[{"name": "Product MM", "price": 19.0, "quantity": 4}]',                               76.0,    'completed',  now() - interval '28 days', now() - interval '28 days'),
  ('b0000000-0000-0000-0000-000000000026', 'EXT-316', 'Laura Gray',    '[{"name": "Product NN", "price": 0.7, "quantity": 3}]',                                2.1,     'completed',  now() - interval '28 days', now() - interval '28 days'),
  ('b0000000-0000-0000-0000-000000000027', 'EXT-317', 'Mike Hughes',   '[{"name": "Product OO", "price": 88.0, "quantity": 2}]',                               176.0,   'completed',  now() - interval '29 days', now() - interval '29 days'),
  ('b0000000-0000-0000-0000-000000000028', 'EXT-318', 'Nancy Ingram',  '[{"name": "Product PP", "price": 0.1, "quantity": 7}]',                                0.7,     'completed',  now() - interval '29 days', now() - interval '29 days'),

  -- failed orders (7)
  ('b0000000-0000-0000-0000-000000000029', 'EXT-401', 'Oscar Jensen',  '[{"name": "Product QQ", "price": 15.0, "quantity": 2}]',                               30.0,    'failed',     now() - interval '10 days', now() - interval '9 days'),
  ('b0000000-0000-0000-0000-00000000002a', 'EXT-402', 'Penny Kim',     '[{"name": "Product RR", "price": 0.2, "quantity": 6}]',                                1.2,     'failed',     now() - interval '13 days', now() - interval '12 days'),
  ('b0000000-0000-0000-0000-00000000002b', 'EXT-403', 'Quinn Long',    '[{"name": "Product SS", "price": 500.0, "quantity": 1}]',                              500.0,   'failed',     now() - interval '16 days', now() - interval '15 days'),
  ('b0000000-0000-0000-0000-00000000002c', 'EXT-404', 'Rachel Morris', '[{"name": "Product TT", "price": 0.1, "quantity": 9}]',                                0.9,     'failed',     now() - interval '19 days', now() - interval '18 days'),
  ('b0000000-0000-0000-0000-00000000002d', 'EXT-405', 'Steve Nelson',  '[{"name": "Product UU", "price": 67.5, "quantity": 2}]',                               135.0,   'failed',     now() - interval '22 days', now() - interval '21 days'),
  ('b0000000-0000-0000-0000-00000000002e', 'EXT-406', 'Teresa Owen',   '[{"name": "Product VV", "price": 0.7, "quantity": 4}]',                                2.8,     'failed',     now() - interval '25 days', now() - interval '24 days'),
  ('b0000000-0000-0000-0000-00000000002f', 'EXT-407', 'Ursula Price',  '[{"name": "Product WW", "price": 12.0, "quantity": 3}, {"name": "Product XX", "price": 0.1, "quantity": 2}]', 36.2, 'failed', now() - interval '28 days', now() - interval '27 days');
