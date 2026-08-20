import type { Metadata } from "next";
import DashboardClient from "./DashboardClient";

export const metadata: Metadata = {
  title: "A+H 股公司研究系统",
  description: "面向 A 股与港股的中期基本面、估值与趋势投研工作台。",
};

export default function Home() {
  return <DashboardClient />;
}
