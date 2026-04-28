import { Outlet } from 'react-router-dom';
import TopBar from './TopBar.jsx';
import NavRail from './NavRail.jsx';
import ChatSidebar from './ChatSidebar.jsx';

export default function AppShell() {
  return (
    <div className="h-screen w-screen flex flex-col bg-canvas overflow-hidden">
      <TopBar />
      <div className="flex-1 flex min-h-0">
        <NavRail />
        <main className="flex-1 min-w-0 overflow-y-auto">
          <Outlet />
        </main>
        <ChatSidebar />
      </div>
    </div>
  );
}
