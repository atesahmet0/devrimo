// Stub veri — Faz 2'de gerçek connector'lar (odtuclass, takvim, webmail) gelir.

export type Announcement = {
  id: string;
  source: string;
  course?: string;
  title: string;
  date: string;
  summary: string;
};

export type ScheduleSlot = {
  id: string;
  day: string;
  start: string;
  end: string;
  course: string;
  code: string;
  place: string;
};

export type MailItem = {
  id: string;
  from: string;
  subject: string;
  date: string;
  preview: string;
  unread: boolean;
};

export const announcements: Announcement[] = [
  {
    id: "a1",
    source: "ODTÜClass",
    course: "CENG 242",
    title: "Ödev 3 yayınlandı",
    date: "2026-08-25",
    summary:
      "Ödev 3 açıklandı, teslim 4 Eylül Cuma 23:59. Late policy: her gün %10.",
  },
  {
    id: "a2",
    source: "Bölüm sayfası",
    title: "2026-2027 Güz dönemi ders programı taslağı",
    date: "2026-08-24",
    summary:
      "Taslak program yayında; itirazlar için bölüm sekreterliğine yazın.",
  },
  {
    id: "a3",
    source: "OIDB",
    title: "Harç ve kayıt yenileme hatırlatması",
    date: "2026-08-22",
    summary: "Kayıt yenileme 31 Ağustos'ta sona eriyor.",
  },
  {
    id: "a4",
    source: "ODTÜClass",
    course: "MATH 260",
    title: "Vize kağıtları görüldü",
    date: "2026-08-20",
    summary: "Vize kağıtları derslikte görülebilir, itiraz süresi 1 hafta.",
  },
];

export const schedule: ScheduleSlot[] = [
  { id: "s1", day: "Pazartesi", start: "09:40", end: "10:30", course: "Matematik II", code: "MATH 120", place: "M-13" },
  { id: "s2", day: "Pazartesi", start: "10:40", end: "12:30", course: "Veri Yapıları", code: "CENG 242", place: "EA-Z01" },
  { id: "s3", day: "Salı", start: "13:40", end: "15:30", course: "Fizik II", code: "PHYS 106", place: "P-02" },
  { id: "s4", day: "Çarşamba", start: "08:40", end: "09:30", course: "İngilizce", code: "ENG 102", place: "D-114" },
  { id: "s5", day: "Çarşamba", start: "09:40", end: "11:30", course: "Veri Yapıları Lab", code: "CENG 242", place: "BLG-Lab" },
  { id: "s6", day: "Perşembe", start: "09:40", end: "11:30", course: "Ayrık Matematik", code: "MATH 260", place: "M-04" },
  { id: "s7", day: "Cuma", start: "10:40", end: "12:30", course: "İstatistik", code: "STAT 201", place: "İ-05" },
];

export const mails: MailItem[] = [
  {
    id: "m1",
    from: "ODTUClass Duyuru <noreply@metu.edu.tr>",
    subject: "[CENG 242] Yeni duyuru: Ödev 3",
    date: "2026-08-25 14:12",
    preview: "Ödev 3 yayınlandı, son teslim tarihi için duyuruya bakın...",
    unread: true,
  },
  {
    id: "m2",
    from: "OIDB <oidb@metu.edu.tr>",
    subject: "Kayıt yenileme hatırlatması",
    date: "2026-08-24 09:03",
    preview: "Sayılı İlgili Öğrenci, kayıt yenilemeniz 31 Ağustos'ta...",
    unread: true,
  },
  {
    id: "m3",
    from: "Kütüphane <kutuphane@metu.edu.tr>",
    subject: "İade hatırlatması: 2 kaynak",
    date: "2026-08-21 16:45",
    preview: "Elinizdeki 2 kaynağın iade tarihi yaklaşmaktadır...",
    unread: false,
  },
];
