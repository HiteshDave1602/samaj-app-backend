import { Palette } from './theme';

// ponytail: static sample data shared by the screens until the member APIs are wired in

export const NEWS = [
  {
    id: '1',
    title: 'Samuh Lagna Sammelan 2026',
    by: 'Ahmedabad City Admin',
    date: '24 Oct 2026',
    color: Palette.secondary,
    body: 'Registrations are open for this year\'s samuh lagna sammelan at the samaj wadi. Families can register at the office or through their city admin before 15 November.\n\nThe sammelan will be held on 8 December with a common mandap, bhojan for all guests and gifts for every couple from the samaj.',
  },
  {
    id: '2',
    title: 'Scholarship forms open for 2026-27',
    by: 'Education Committee',
    date: '20 Oct 2026',
    color: Palette.primary,
    body: 'Students from samaj families studying in class 10 and above can apply for this year\'s scholarship. Attach your latest marksheet and fee receipt.\n\nForms close on 30 November. Results will be announced at the annual sneh milan.',
  },
  {
    id: '3',
    title: 'Navratri Garba at the samaj hall',
    by: 'Surat City Admin',
    date: '2 Oct 2026',
    color: Palette.brand,
    body: 'All nine nights of garba will be held at the samaj hall from 8 PM. Entry passes are free for members and can be collected from the office.\n\nPrizes for best dressed and best garba will be given on the last night.',
  },
];

export const PROFILES = [
  { id: 'p1', name: 'Meera Shah', age: 26, city: 'Ahmedabad', education: 'Postgraduate · M.Com', profession: 'Chartered Accountant', gotra: 'Kashyap', native: 'Visnagar', about: 'Close-knit family, enjoys music and travel.' },
  { id: 'p2', name: 'Riya Patel', age: 25, city: 'Surat', education: 'Graduate · B.Tech', profession: 'Software Engineer', gotra: 'Bharadwaj', native: 'Mehsana', about: 'Works in Bengaluru, loves cooking and reading.' },
  { id: 'p3', name: 'Nisha Desai', age: 27, city: 'Vadodara', education: 'Postgraduate · MBA', profession: 'Marketing Manager', gotra: 'Vatsa', native: 'Patan', about: 'Outgoing, values family traditions.' },
  { id: 'p4', name: 'Kavya Mehta', age: 24, city: 'Rajkot', education: 'Graduate · B.Pharm', profession: 'Pharmacist', gotra: 'Gautam', native: 'Morbi', about: 'Calm and caring, enjoys garba and painting.' },
];

// profiles that asked to see this member's biodata
export const BIODATA_REQUESTS = ['p1', 'p2', 'p3'];

export const ME = {
  name: 'Kamya Patel',
  age: 24,
  gender: 'Female',
  profession: 'Software Engineer',
  gotra: 'Kashyap',
  city: 'Ahmedabad',
};

// mirrors samaj.member: only ACTIVE (admin-approved) members belong in the directory
export const MEMBERS: {
  id: string;
  name: string;
  gender: 'Male' | 'Female';
  city: string;
  gotra: string;
  profession: string;
  phone: string;
  hidePhone: boolean;
  status: 'ACTIVE' | 'PENDING' | 'REJECTED';
}[] = [
  { id: 'm1', name: 'Rajesh Patel', gender: 'Male', city: 'Ahmedabad', gotra: 'Kashyap', profession: 'Textile Business', phone: '+91 98250 11223', hidePhone: false, status: 'ACTIVE' },
  { id: 'm2', name: 'Meera Shah', gender: 'Female', city: 'Ahmedabad', gotra: 'Kashyap', profession: 'Chartered Accountant', phone: '+91 98790 44556', hidePhone: true, status: 'ACTIVE' },
  { id: 'm3', name: 'Hitesh Desai', gender: 'Male', city: 'Surat', gotra: 'Vatsa', profession: 'Diamond Trader', phone: '+91 99099 77881', hidePhone: false, status: 'ACTIVE' },
  { id: 'm4', name: 'Riya Patel', gender: 'Female', city: 'Surat', gotra: 'Bharadwaj', profession: 'Software Engineer', phone: '+91 97234 55667', hidePhone: false, status: 'ACTIVE' },
  { id: 'm5', name: 'Nilesh Mehta', gender: 'Male', city: 'Vadodara', gotra: 'Gautam', profession: 'Doctor', phone: '+91 98980 33445', hidePhone: false, status: 'ACTIVE' },
  { id: 'm6', name: 'Kavya Mehta', gender: 'Female', city: 'Rajkot', gotra: 'Gautam', profession: 'Pharmacist', phone: '+91 96012 88990', hidePhone: true, status: 'ACTIVE' },
  { id: 'm7', name: 'Bharat Joshi', gender: 'Male', city: 'Rajkot', gotra: 'Bharadwaj', profession: 'School Teacher', phone: '+91 94260 12121', hidePhone: false, status: 'ACTIVE' },
  { id: 'm8', name: 'Sanjay Trivedi', gender: 'Male', city: 'Vadodara', gotra: 'Vatsa', profession: 'Civil Engineer', phone: '+91 93270 45454', hidePhone: false, status: 'PENDING' },
];

export const RELATIONS = ['Father', 'Mother', 'Spouse', 'Brother', 'Sister', 'Son', 'Daughter', 'Grandfather', 'Grandmother'] as const;

export const FAMILY: { id: string; name: string; relation: (typeof RELATIONS)[number]; status: 'APPROVED' | 'PENDING' }[] = [
  { id: 'f1', name: 'Rajesh Patel', relation: 'Father', status: 'APPROVED' },
  { id: 'f2', name: 'Hema Patel', relation: 'Mother', status: 'APPROVED' },
  { id: 'f3', name: 'Arjun Patel', relation: 'Brother', status: 'APPROVED' },
  { id: 'f4', name: 'Kantilal Patel', relation: 'Grandfather', status: 'APPROVED' },
  { id: 'f5', name: 'Savita Patel', relation: 'Grandmother', status: 'PENDING' },
];
