export type TravelStyle = "relaxed" | "classic" | "deep" | "family" | "foodie";
export type BudgetLevel = "economy" | "standard" | "comfort";

export interface TripRequest {
  destination: string;
  days: number;
  people: number;
  budget_level: BudgetLevel;
  travel_style: TravelStyle;
  interests: string[];
  start_date?: string | null;
  notes: string;
  /** 会话记忆标识：localStorage 持久化，多轮规划沿用历史偏好 */
  session_id?: string | null;
}

export interface Place {
  name: string;
  category: string;
  description: string;
  lat: number;
  lng: number;
  estimated_hours: number;
  ticket: number;
}

export interface DayPlan {
  day: number;
  theme: string;
  morning: Place;
  afternoon: Place;
  evening: Place;
  transport: string;
  meals: string[];
  estimated_cost: number;
  teacher_note: string;
}

export interface BudgetBreakdown {
  lodging: number;
  food: number;
  transport: number;
  tickets: number;
  misc: number;
  total: number;
  per_person: number;
}

export interface TripPlan {
  title: string;
  destination: string;
  summary: string;
  request: TripRequest;
  days: DayPlan[];
  budget: BudgetBreakdown;
  route_points: Place[];
  packing_list: string[];
  tips: string[];
  /** 会话记忆回显：如「已记住你的偏好：历史、美食」 */
  memory_notes?: string[];
}
