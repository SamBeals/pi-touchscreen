import QtQuick
import QtQuick.Layouts
import SellMate 1.0

Item {
    id: root
    property string title: ""
    property bool showCart: false
    property bool showBrand: true
    readonly property bool showLogo: showBrand
        && Theme.logoUrl.length > 0
        && (Theme.logoPlacement === "header" || Theme.logoPlacement === "both")
    implicitHeight: row.implicitHeight

    RowLayout {
        id: row
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: Theme.gap

        // Balance the cart chip so the brand column stays visually centered.
        Item {
            visible: root.showCart
            Layout.preferredWidth: cartChip.Layout.preferredWidth
            Layout.preferredHeight: 1
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.gap

            // Top line: Powered by SellMate (SellMate in brand lime).
            Text {
                visible: root.showBrand
                text: "Powered by <font color=\"" + Theme.primary + "\">SellMate</font>"
                textFormat: Text.RichText
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Math.max(12, Theme.bodyFontPx - 2)
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
            }

            // Large centered logo below the powered-by line.
            Image {
                visible: root.showLogo
                source: Theme.logoUrl
                Layout.preferredHeight: Math.max(Theme.titleFontPx * 2.4, 110)
                Layout.preferredWidth: Math.min(parent.width * 0.88, 360)
                Layout.maximumHeight: 160
                Layout.alignment: Qt.AlignHCenter
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }

            // Fallback when no logo is configured for the header.
            Text {
                visible: root.showBrand && !root.showLogo
                text: Theme.businessName
                color: Theme.primary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.titleFontPx
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
            }

            // Non-brand screens (Detail / Cart) still use a plain title.
            Text {
                visible: root.title.length > 0 && !root.showBrand
                text: root.title
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.titleFontPx - 4
                font.bold: true
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        Rectangle {
            id: cartChip
            visible: root.showCart
            Layout.preferredHeight: Theme.secondaryButtonMinHeight
            Layout.preferredWidth: Math.max(cartLabel.implicitWidth + 44, 120)
            Layout.alignment: Qt.AlignTop
            radius: height / 2
            color: Theme.secondary
            border.color: Theme.border
            border.width: 1

            scale: cartMa.pressed ? 0.97 : 1.0
            Behavior on scale {
                NumberAnimation { duration: Math.max(80, Theme.animationMs / 2); easing.type: Easing.OutCubic }
            }

            Text {
                id: cartLabel
                anchors.centerIn: parent
                text: "Cart · " + App.cartCount
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx
                font.bold: true
            }

            MouseArea {
                id: cartMa
                anchors.fill: parent
                onClicked: {
                    App.bumpIdle()
                    App.openCart()
                }
            }
        }
    }
}
