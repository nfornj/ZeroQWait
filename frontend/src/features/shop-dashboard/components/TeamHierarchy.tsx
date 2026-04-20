import * as React from 'react';
import clsx from 'clsx';
import { animated, useSpring } from '@react-spring/web';
import { TransitionProps } from '@mui/material/transitions';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Collapse from '@mui/material/Collapse';
import Typography from '@mui/material/Typography';
import { RichTreeView } from '@mui/x-tree-view/RichTreeView';
import { useTreeItem, UseTreeItemParameters } from '@mui/x-tree-view/useTreeItem';
import {
    TreeItemContent,
    TreeItemIconContainer,
    TreeItemLabel,
    TreeItemRoot,
} from '@mui/x-tree-view/TreeItem';
import { TreeItemIcon } from '@mui/x-tree-view/TreeItemIcon';
import { TreeItemProvider } from '@mui/x-tree-view/TreeItemProvider';
import { TreeViewBaseItem } from '@mui/x-tree-view/models';
import { useTheme } from '@mui/material/styles';
import api from '../../../services/api';
import { useShop } from '../../../contexts/ShopContext';

type Color = 'blue' | 'green' | 'red';

type ExtendedTreeItemProps = {
    color?: Color;
    id: string;
    label: string;
};

// ... (Reusing styling components)
function DotIcon({ color }: { color: string }) {
    return (
        <Box sx={{ marginRight: 1, display: 'flex', alignItems: 'center' }}>
            <svg width={6} height={6}>
                <circle cx={3} cy={3} r={3} fill={color} />
            </svg>
        </Box>
    );
}

const AnimatedCollapse = animated(Collapse);

function TransitionComponent(props: TransitionProps) {
    const style = useSpring({
        to: {
            opacity: props.in ? 1 : 0,
            transform: `translate3d(0,${props.in ? 0 : 20}px,0)`,
        },
    });

    return <AnimatedCollapse style={style} {...props} />;
}

interface CustomLabelProps {
    children: React.ReactNode;
    color?: Color;
    expandable?: boolean;
}

function CustomLabel({ color, expandable, children, ...other }: CustomLabelProps) {
    const theme = useTheme();
    const colors = {
        blue: (theme.palette as any).primary.main,
        green: (theme.palette as any).success.main,
        red: (theme.palette as any).error.main,
    };

    const iconColor = color ? colors[color] : null;
    return (
        <TreeItemLabel {...other} sx={{ display: 'flex', alignItems: 'center' }}>
            {iconColor && <DotIcon color={iconColor} />}
            <Typography
                className="labelText"
                variant="body2"
                sx={{ color: 'text.primary' }}
            >
                {children}
            </Typography>
        </TreeItemLabel>
    );
}

interface CustomTreeItemProps
    extends
    Omit<UseTreeItemParameters, 'rootRef'>,
    Omit<React.HTMLAttributes<HTMLLIElement>, 'onFocus'> { }

const CustomTreeItem = React.forwardRef(function CustomTreeItem(
    props: CustomTreeItemProps,
    ref: React.Ref<HTMLLIElement>,
) {
    const { id, itemId, label, disabled, children, ...other } = props;

    const {
        getRootProps,
        getContentProps,
        getIconContainerProps,
        getLabelProps,
        getGroupTransitionProps,
        status,
        publicAPI,
    } = useTreeItem({ id, itemId, children, label, disabled, rootRef: ref });

    const item = publicAPI.getItem(itemId);
    const color = item?.color;
    return (
        <TreeItemProvider id={id} itemId={itemId}>
            <TreeItemRoot {...getRootProps(other)}>
                <TreeItemContent
                    {...getContentProps({
                        className: clsx('content', {
                            expanded: status.expanded,
                            selected: status.selected,
                            focused: status.focused,
                            disabled: status.disabled,
                        }),
                    })}
                >
                    {status.expandable && (
                        <TreeItemIconContainer {...getIconContainerProps()}>
                            <TreeItemIcon status={status} />
                        </TreeItemIconContainer>
                    )}

                    <CustomLabel {...getLabelProps({ color })} />
                </TreeItemContent>
                {children && (
                    <TransitionComponent
                        {...getGroupTransitionProps({ className: 'groupTransition' })}
                    />
                )}
            </TreeItemRoot>
        </TreeItemProvider>
    );
});

export default function TeamHierarchy() {
    const { shop } = useShop();
    const [items, setItems] = React.useState<TreeViewBaseItem<ExtendedTreeItemProps>[]>([]);

    React.useEffect(() => {
        const fetchTeam = async () => {
            if (!shop) return;
            try {
                // Fetch employees
                const empResponse = await api.get(`/shops/${shop.id}/employees`);
                const employees = empResponse.data;

                // Separate by role
                const managers = employees.filter((e: any) => e.user.role === 'manager');
                const regularEmployees = employees.filter((e: any) => e.user.role === 'employee');

                // Construct tree
                const tree: TreeViewBaseItem<ExtendedTreeItemProps>[] = [
                    {
                        id: 'owner',
                        label: 'Owner (You)',
                        color: 'blue',
                        children: []
                    }
                ];

                // Add Managers
                if (managers.length > 0) {
                    tree.push({
                        id: 'managers',
                        label: 'Managers',
                        children: managers.map((m: any) => ({
                            id: `m-${m.user.id}`,
                            label: m.user.username,
                            color: 'green'
                        }))
                    });
                }

                // Add Employees
                if (regularEmployees.length > 0) {
                    tree.push({
                        id: 'employees',
                        label: 'Employees',
                        children: regularEmployees.map((e: any) => ({
                            id: `e-${e.user.id}`,
                            label: e.user.username,
                            color: 'green'
                        }))
                    });
                }

                setItems(tree);

            } catch (err) {
                console.error("Failed to fetch team hierarchy", err);
            }
        };
        fetchTeam();
    }, [shop]);

    return (
        <Card
            variant="outlined"
            sx={{ display: 'flex', flexDirection: 'column', gap: '8px', flexGrow: 1, bgcolor: 'var(--owner-glass-bg)', backdropFilter: 'blur(20px)', borderColor: 'var(--owner-glass-border)', boxShadow: 'var(--owner-glass-shadow)' }}
        >
            <CardContent>
                <Typography component="h2" variant="subtitle2">
                    Team Hierarchy
                </Typography>
                <RichTreeView
                    items={items}
                    aria-label="team hierarchy"
                    defaultExpandedItems={['managers', 'employees']}
                    sx={{
                        m: '0 -8px',
                        pb: '8px',
                        height: 'fit-content',
                        flexGrow: 1,
                        overflowY: 'auto',
                    }}
                    slots={{ item: CustomTreeItem }}
                />
            </CardContent>
        </Card>
    );
}
