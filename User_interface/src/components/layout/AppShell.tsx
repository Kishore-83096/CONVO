import { Outlet } from "react-router-dom";

import { LeftSidebar } from "./LeftSidebar";
import { MainContent } from "./MainContent";
import { RightSidebar } from "./RightSidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
    return (
        <div className="app-shell">

            <TopBar />

            <div className="workspace">

                <LeftSidebar />

                <MainContent>
                    <Outlet />
                </MainContent>

                <RightSidebar />

            </div>

        </div>
    );
}