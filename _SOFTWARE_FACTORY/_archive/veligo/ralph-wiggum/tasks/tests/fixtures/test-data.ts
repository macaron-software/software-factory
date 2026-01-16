export const tenants = [
  { id: 'tenant-idfm', name: 'Île-de-France Mobilités', slug: 'idfm' },
  { id: 'tenant-nantes', name: 'Nantes Métropole', slug: 'nantes' },
  { id: 'tenant-lyon', name: 'TCL Lyon', slug: 'lyon' }
];

export const users = {
  USER_IDFM: {
    id: 'user-idfm-001',
    email: 'marie.dupont@test-idfm.fr',
    password: 'Test2025!Secure',
    firstName: 'Marie',
    lastName: 'Dupont',
    phone: '0612345678',
    tenant: 'idfm',
    role: 'user'
  },
  ADMIN_IDFM: {
    id: 'admin-idfm-001',
    email: 'admin@idfm.fr',
    password: 'AdminTest2025!',
    firstName: 'Admin',
    lastName: 'IDFM',
    tenant: 'idfm',
    role: 'admin'
  },
  USER_NANTES: {
    id: 'user-nantes-001',
    email: 'jean.martin@test-nantes.fr',
    password: 'Test2025!Secure',
    firstName: 'Jean',
    lastName: 'Martin',
    phone: '0698765432',
    tenant: 'nantes',
    role: 'user'
  },
  USER_LYON: {
    id: 'user-lyon-001',
    email: 'pierre.bernard@test-lyon.fr',
    password: 'Test2025!Secure',
    firstName: 'Pierre',
    lastName: 'Bernard',
    phone: '0654321098',
    tenant: 'lyon',
    role: 'user'
  }
};

export const plans = [
  {
    id: 'basic',
    name: 'Découverte',
    description: 'Idéal pour essayer le service',
    price: 0,
    duration: 'month',
    bikeType: 'manual',
    features: ['Vélo mécanique', 'Assistance téléphone', 'Casque offert']
  },
  {
    id: 'standard',
    name: 'Standard',
    description: 'Notre offre la plus populaire',
    price: 40,
    duration: 'month',
    bikeType: 'electric',
    features: ['Vélo électrique', 'Assistance prioritaire', 'Casque et antivol offerts', 'Maintenance incluse']
  },
  {
    id: 'premium',
    name: 'Premium',
    description: 'Pour les professionnels et familles',
    price: 80,
    duration: 'month',
    bikeType: 'cargo',
    features: ['Vélo cargo électrique', 'Assistance 24/7', 'Équipement complet', 'Remplacement express', 'Assurance tous risques']
  }
];

export const stations = {
  idfm: [
    {
      id: '50000000-0000-0000-0000-000000000001',
      name: 'Gare de Lyon - Veloparc',
      address: '20 Boulevard Diderot, 75012 Paris',
      latitude: 48.8448,
      longitude: 2.3735,
      capacity: 50,
      availableBikes: 2,
      availableSlots: 45,
      status: 'active',
      type: 'veloparc'
    },
    {
      id: '50000000-0000-0000-0000-000000000002',
      name: 'La Defense - Grande Arche',
      address: '1 Parvis de la Defense, 92800 Puteaux',
      latitude: 48.8920,
      longitude: 2.2362,
      capacity: 30,
      availableBikes: 1,
      availableSlots: 26,
      status: 'active',
      type: 'veloparc'
    }
  ],
  nantes: [
    {
      id: '50000000-0000-0000-0000-000000000004',
      name: 'Gare de Nantes - Nord',
      address: '27 Boulevard de Stalingrad, 44000 Nantes',
      latitude: 47.2173,
      longitude: -1.5416,
      capacity: 40,
      availableBikes: 1,
      availableSlots: 35,
      status: 'active',
      type: 'box'
    }
  ],
  lyon: [
    {
      id: '50000000-0000-0000-0000-000000000006',
      name: 'Part-Dieu - Gare',
      address: '5 Place Charles Beraudier, 69003 Lyon',
      latitude: 45.7606,
      longitude: 4.8600,
      capacity: 60,
      availableBikes: 2,
      availableSlots: 50,
      status: 'active',
      type: 'veloparc'
    }
  ]
};

export const bikes = {
  idfm: [
    { id: 'IDFM-VAE-001', code: 'IDFM-VAE-001', type: 'electric', model: 'Veligo VAE Standard', status: 'available' },
    { id: 'IDFM-VAE-002', code: 'IDFM-VAE-002', type: 'electric', model: 'Veligo VAE Standard', status: 'available' },
    { id: 'IDFM-CARGO-001', code: 'IDFM-CARGO-001', type: 'cargo', model: 'Veligo Cargo Pro', status: 'available' },
    { id: 'IDFM-MECH-001', code: 'IDFM-MECH-001', type: 'mechanical', model: 'Veligo Classic', status: 'available' }
  ],
  nantes: [
    { id: 'NANTES-VAE-001', code: 'NANTES-VAE-001', type: 'electric', model: 'Naolib VAE City', status: 'available' }
  ],
  lyon: [
    { id: 'LYON-VAE-001', code: 'LYON-VAE-001', type: 'electric', model: 'TCL velo+ Electrique', status: 'available' }
  ]
};

export const bookings = {
  idfm: [
    { id: 'booking-idfm-001', userId: 'user-idfm-001', bikeId: 'IDFM-VAE-001', status: 'completed' }
  ],
  nantes: [
    { id: 'booking-nantes-001', userId: 'user-nantes-001', bikeId: 'NANTES-VAE-001', status: 'completed' }
  ],
  lyon: [
    { id: 'booking-lyon-001', userId: 'user-lyon-001', bikeId: 'LYON-VAE-001', status: 'completed' }
  ]
};
