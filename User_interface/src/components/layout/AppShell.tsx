import { Outlet } from "react-router-dom";

import { LeftSidebar } from "./LeftSidebar";
import { MainContent } from "./MainContent";

export function AppShell() {
    return (
        <div className="app-shell myna-shell">
            <LeftSidebar />
            <MainContent>
                <Outlet />
            </MainContent>
        </div>
    );
}
