import type { ReactNode } from "react";

type MainContentProps = {
    children: ReactNode;
};

export function MainContent({
    children,
}: MainContentProps) {
    return (
        <main className="main-body">
            {children}
        </main>
    );
}
