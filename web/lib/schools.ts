// Supported schools: the 18 Big Ten members (since August 2024), plus NYU, which is not in the
// Big Ten. Office URLs were checked on 2026-11-27; re-check them when you re-verify the rules.
// `city` scopes map searches, `domain` scopes "search this school's site" links, and
// `airports` lists the usual arrival airports.

export interface Airport {
  code: string;
  name: string;
}

export interface School {
  id: string;
  name: string;
  short: string;
  mono: string; // monogram for the picker; no logos or trademarked marks
  city: string;
  domain: string;
  office: string;
  url: string;
  airports: Airport[];
  group: "bigten" | "other";
}

export const SCHOOLS: School[] = [
  { id: "illinois", name: "University of Illinois Urbana-Champaign", short: "Illinois", mono: "IL",
    city: "Champaign, IL", domain: "illinois.edu",
    office: "International Student and Scholar Services", url: "https://isss.illinois.edu/",
    airports: [{ code: "CMI", name: "University of Illinois Willard Airport" }, { code: "ORD", name: "Chicago O'Hare International" }],
    group: "bigten" },
  { id: "indiana", name: "Indiana University Bloomington", short: "Indiana", mono: "IU",
    city: "Bloomington, IN", domain: "iu.edu",
    office: "Office of International Services", url: "https://ois.iu.edu/",
    airports: [{ code: "IND", name: "Indianapolis International" }], group: "bigten" },
  { id: "iowa", name: "University of Iowa", short: "Iowa", mono: "UI",
    city: "Iowa City, IA", domain: "uiowa.edu",
    office: "International Student and Scholar Services", url: "https://international.uiowa.edu/isss",
    airports: [{ code: "CID", name: "The Eastern Iowa Airport (Cedar Rapids)" }], group: "bigten" },
  { id: "maryland", name: "University of Maryland, College Park", short: "Maryland", mono: "UMD",
    city: "College Park, MD", domain: "umd.edu",
    office: "International Student & Scholar Services", url: "https://isss.umd.edu/",
    airports: [{ code: "BWI", name: "Baltimore/Washington International" }, { code: "DCA", name: "Reagan Washington National" },
      { code: "IAD", name: "Washington Dulles International" }], group: "bigten" },
  { id: "michigan", name: "University of Michigan", short: "Michigan", mono: "UM",
    city: "Ann Arbor, MI", domain: "umich.edu",
    office: "International Center", url: "https://internationalcenter.umich.edu/",
    airports: [{ code: "DTW", name: "Detroit Metropolitan Wayne County" }], group: "bigten" },
  { id: "michigan-state", name: "Michigan State University", short: "Michigan State", mono: "MSU",
    city: "East Lansing, MI", domain: "msu.edu",
    office: "Office for International Students and Scholars", url: "https://oiss.isp.msu.edu/",
    airports: [{ code: "LAN", name: "Capital Region International (Lansing)" }, { code: "DTW", name: "Detroit Metropolitan Wayne County" }],
    group: "bigten" },
  { id: "minnesota", name: "University of Minnesota Twin Cities", short: "Minnesota", mono: "UMN",
    city: "Minneapolis, MN", domain: "umn.edu",
    office: "International Student and Scholar Services", url: "https://isss.umn.edu/",
    airports: [{ code: "MSP", name: "Minneapolis–St. Paul International" }], group: "bigten" },
  { id: "nebraska", name: "University of Nebraska–Lincoln", short: "Nebraska", mono: "UNL",
    city: "Lincoln, NE", domain: "unl.edu",
    office: "International Student and Scholar Office", url: "https://global.unl.edu/isso/",
    airports: [{ code: "LNK", name: "Lincoln Airport" }, { code: "OMA", name: "Eppley Airfield (Omaha)" }], group: "bigten" },
  { id: "northwestern", name: "Northwestern University", short: "Northwestern", mono: "NU",
    city: "Evanston, IL", domain: "northwestern.edu",
    office: "Office of International Student and Scholar Services", url: "https://www.northwestern.edu/international/",
    airports: [{ code: "ORD", name: "Chicago O'Hare International" }, { code: "MDW", name: "Chicago Midway International" }],
    group: "bigten" },
  { id: "ohio-state", name: "The Ohio State University", short: "Ohio State", mono: "OSU",
    city: "Columbus, OH", domain: "osu.edu",
    office: "Office of International Affairs", url: "https://oia.osu.edu/",
    airports: [{ code: "CMH", name: "John Glenn Columbus International" }], group: "bigten" },
  { id: "oregon", name: "University of Oregon", short: "Oregon", mono: "UO",
    city: "Eugene, OR", domain: "uoregon.edu",
    office: "International Student & Scholar Services", url: "https://isss.uoregon.edu/",
    airports: [{ code: "EUG", name: "Eugene Airport" }, { code: "PDX", name: "Portland International" }], group: "bigten" },
  { id: "penn-state", name: "Penn State University", short: "Penn State", mono: "PSU",
    city: "State College, PA", domain: "psu.edu",
    office: "International Student and Scholar Advising, Penn State Global", url: "https://global.psu.edu/category/international-students",
    airports: [{ code: "SCE", name: "State College Regional" }, { code: "PIT", name: "Pittsburgh International" }], group: "bigten" },
  { id: "purdue", name: "Purdue University", short: "Purdue", mono: "PU",
    city: "West Lafayette, IN", domain: "purdue.edu",
    office: "Office of International Students and Scholars", url: "https://www.purdue.edu/gpp/iss/",
    airports: [{ code: "IND", name: "Indianapolis International" }, { code: "ORD", name: "Chicago O'Hare International" }],
    group: "bigten" },
  { id: "rutgers", name: "Rutgers University–New Brunswick", short: "Rutgers", mono: "RU",
    city: "New Brunswick, NJ", domain: "rutgers.edu",
    office: "Rutgers Global – International Student and Scholar Services", url: "https://global.rutgers.edu/",
    airports: [{ code: "EWR", name: "Newark Liberty International" }, { code: "JFK", name: "John F. Kennedy International" }],
    group: "bigten" },
  { id: "ucla", name: "University of California, Los Angeles", short: "UCLA", mono: "UCLA",
    city: "Westwood, Los Angeles, CA", domain: "ucla.edu",
    office: "Dashew Center for International Students & Scholars", url: "https://internationalcenter.ucla.edu/f-1-students",
    airports: [{ code: "LAX", name: "Los Angeles International" }], group: "bigten" },
  { id: "usc", name: "University of Southern California", short: "USC", mono: "USC",
    city: "University Park, Los Angeles, CA", domain: "usc.edu",
    office: "Office of International Services", url: "https://ois.usc.edu/",
    airports: [{ code: "LAX", name: "Los Angeles International" }], group: "bigten" },
  { id: "washington", name: "University of Washington", short: "Washington", mono: "UW",
    city: "Seattle, WA", domain: "washington.edu",
    office: "International Student Services", url: "https://iss.washington.edu/",
    airports: [{ code: "SEA", name: "Seattle–Tacoma International" }], group: "bigten" },
  { id: "wisconsin", name: "University of Wisconsin–Madison", short: "Wisconsin", mono: "UWM",
    city: "Madison, WI", domain: "wisc.edu",
    office: "International Student Services", url: "https://iss.wisc.edu/",
    airports: [{ code: "MSN", name: "Dane County Regional (Madison)" }, { code: "ORD", name: "Chicago O'Hare International" }],
    group: "bigten" },
  { id: "nyu", name: "New York University", short: "NYU", mono: "NYU",
    city: "Manhattan, New York, NY", domain: "nyu.edu",
    office: "Office of Global Services",
    url: "https://www.nyu.edu/students/student-information-and-resources/student-visa-and-immigration.html",
    airports: [{ code: "JFK", name: "John F. Kennedy International" }, { code: "LGA", name: "LaGuardia" },
      { code: "EWR", name: "Newark Liberty International" }], group: "other" },
];

export function findSchool(id: string | null | undefined): School | null {
  return SCHOOLS.find((s) => s.id === id) ?? null;
}
